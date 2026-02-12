"""Commands for managing ADE-bench tasks."""

import typer
import yaml
from pathlib import Path
from typing import Annotated
from rich.console import Console
from rich.table import Table

tasks_app = typer.Typer(help="Manage ADE-bench tasks")

@tasks_app.command()
def list(
    tasks_dir: Annotated[
        Path, typer.Option(help="The path to the tasks directory.")
    ] = Path("tasks"),
    copy: Annotated[
        bool, typer.Option(help="Copy task details as TSV to clipboard")
    ] = False,
):
    """List available tasks with their details and prompts."""
    import pandas as pd
    import subprocess
    import sys

    if not tasks_dir.exists():
        typer.echo(f"Tasks directory {tasks_dir} does not exist.")
        raise typer.Exit(code=1)

    # Get all task directories, excluding .template and any hidden directories
    tasks = [d for d in tasks_dir.iterdir()
             if d.is_dir() and not d.name.startswith('.') and d.name != '.template']

    if not tasks:
        typer.echo("No tasks found.")
        raise typer.Exit(code=0)

    # Create a console to get terminal width
    console = Console()
    terminal_width = console.width

    # Calculate available width for prompt column (subtracting fixed columns and padding)
    # Status (6) + Task ID (30) + padding/borders (approx 10) = 46
    prompt_width = max(terminal_width - 46, 40)  # At least 40 chars even on small terminals

    # Create a table
    table = Table(title="Available ADE-bench Tasks", expand=True)
    table.add_column("Status", style="magenta", width=6)
    table.add_column("Task ID", style="cyan", no_wrap=True, width=30)
    table.add_column("Prompt", no_wrap=True)

    # Prepare data for table and TSV export
    all_task_data = []
    unique_tags = set()
    difficulties = set()
    unique_task_ids = set()

    # Function to clean text for display and export
    def clean_text(text):
        if not text:
            return ""
        # Remove line breaks and normalize whitespace
        cleaned = ' '.join(str(text).split())
        # Remove any control characters that might cause issues
        cleaned = ''.join(char for char in cleaned if ord(char) >= 32 or char in '\t\n\r')
        return cleaned

    # Function to truncate middle of text with ellipsis to fit available space
    def truncate_middle(text, max_length):
        if not text or len(text) <= max_length:
            return text

        # Calculate how much text to show from beginning and end
        half_length = (max_length - 3) // 2  # 3 for ellipsis
        begin = text[:half_length]
        end = text[-half_length:]

        return f"{begin}...{end}"

    # Populate table with tasks
    for task_path in sorted(tasks):
        task_yaml = task_path / "task.yaml"
        if not task_yaml.exists():
            continue

        try:
            with open(task_yaml, "r") as f:
                task_data = yaml.safe_load(f)
                base_task_id = task_path.name
                unique_task_ids.add(base_task_id)

                description = clean_text(task_data.get("description", "No description"))
                status = clean_text(task_data.get("status", "unknown"))
                difficulty = clean_text(task_data.get("difficulty", "unknown"))
                tags = task_data.get("tags", [])
                tags_str = ", ".join(tags) if tags else ""

                # Add to collections for summary
                difficulties.add(difficulty)
                for tag in tags:
                    unique_tags.add(tag)

                # Extract variant information
                variants = task_data.get("variants", [])

                # Extract all the fields needed for TSV export
                db_types = ", ".join(sorted(set([v.get('db_type', '') for v in variants if v.get('db_type')])))
                project_types = ", ".join(sorted(set([v.get('project_type', '') for v in variants if v.get('project_type')])))
                project_name = ", ".join(sorted(set([v.get('project_name', '') for v in variants if v.get('project_name')])))
                database_name = ", ".join(sorted(set([v.get('db_name', '') for v in variants if v.get('db_name')])))
                notes = clean_text(task_data.get('notes', ''))

                # Get prompts
                prompts = task_data.get("prompts", [])

                if not prompts:
                    # Use description as prompt when no prompt is available
                    truncated_description = truncate_middle(description, prompt_width)

                    # Format status with proper color
                    formatted_status = f"[green]{status}[/green]" if status.lower() == "ready" else status

                    table.add_row(
                        formatted_status,
                        base_task_id,
                        truncated_description
                    )

                    # Store data for TSV export
                    all_task_data.append({
                        'status': status,
                        'task_id': base_task_id,
                        'database_types': db_types,
                        'project_types': project_types,
                        'project_name': project_name,
                        'database_name': database_name,
                        'key': "",
                        'description': description,
                        'prompt': "",
                        'notes': notes,
                        'difficulty': difficulty,
                        'tags': tags_str
                    })
                else:
                    # Create one row per prompt key
                    for idx, prompt in enumerate(prompts):
                        key = clean_text(prompt.get('key', ''))
                        prompt_text = clean_text(prompt.get('prompt', ''))

                        # Truncate the prompt text with ellipsis in middle using dynamic width
                        truncated_prompt = truncate_middle(prompt_text, prompt_width)

                        # Determine if this is the base key or a variant
                        is_base = (key == "" or key.lower() == "base")

                        # Build display task_id: append key if not base
                        if is_base:
                            display_task_id = base_task_id
                        else:
                            display_task_id = f"{base_task_id}.{key}"

                        # Format status: show status for base, arrow for variants
                        if is_base:
                            formatted_status = f"[green]{status}[/green]" if status.lower() == "ready" else status
                        else:
                            formatted_status = "[grey70]  ↳[/grey70]"

                        table.add_row(
                            formatted_status,
                            display_task_id,
                            truncated_prompt
                        )

                        # Store full data for TSV export
                        all_task_data.append({
                            'status': status,
                            'task_id': base_task_id,
                            'database_types': db_types,
                            'project_types': project_types,
                            'project_name': project_name,
                            'database_name': database_name,
                            'key': key,
                            'description': description,
                            'prompt': prompt_text,
                            'notes': notes,
                            'difficulty': difficulty,
                            'tags': tags_str
                        })

        except Exception:
            # Add error row
            table.add_row(
                "[red]error[/red]",
                task_path.name,
                "[red]Error loading task.yaml[/red]"
            )

    # Print the table
    console.print(table)

    # Print summary
    console.print("\n[bold]Summary:[/bold]")
    console.print(f"Total tasks: {len(unique_task_ids)}")
    console.print(f"Total rows (with prompts): {len(all_task_data)}")
    console.print(f"Difficulties: {', '.join(sorted(difficulties))}")
    console.print(f"Tags: {', '.join(sorted(unique_tags))}")

    # Handle clipboard copy if requested
    if copy:
        try:
            # Create DataFrame and TSV content
            df = pd.DataFrame(all_task_data)
            # Order columns like in the original extract_task_details.py script
            column_order = [
                'status',
                'task_id',
                'database_types',
                'project_types',
                'project_name',
                'database_name',
                'key',
                'description',
                'prompt',
                'notes',
                'difficulty',
                'tags'
            ]
            df = df[column_order]
            # Sort by task_id and key like extract_task_details.py
            df = df.sort_values(['task_id', 'key'])
            tsv_content = df.to_csv(index=False, sep='\t')

            # Copy to clipboard based on platform
            copy_success = False
            if sys.platform == "darwin":  # macOS
                process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE, text=True)
                process.communicate(input=tsv_content)
                copy_success = True
            elif sys.platform.startswith('linux'):  # Linux
                process = subprocess.Popen(['xclip', '-selection', 'clipboard'], stdin=subprocess.PIPE, text=True)
                process.communicate(input=tsv_content)
                copy_success = True

            if copy_success:
                console.print("\n[green]TSV copied to clipboard[/green]")
            else:
                console.print("\n[yellow]Clipboard copy not supported on this platform[/yellow]")
        except ImportError:
            console.print("\n[red]Error: pandas required for TSV export. Install with: pip install pandas[/red]")
        except Exception as e:
            console.print(f"\n[red]Error copying to clipboard: {str(e)}[/red]")
    else:
        console.print("\n[dim]Tip: Use --copy to copy task details as TSV to clipboard[/dim]")
