"""Commands for managing ADE-bench tasks."""

from __future__ import annotations

import typer
from pathlib import Path
from typing import Annotated
from rich.console import Console
from rich.table import Table

from ade_bench.utils.task_scanner import TaskInfo, TaskScanner

tasks_app = typer.Typer(help="Manage ADE-bench tasks")


def _clean_text(text: str | None) -> str:
    """Remove line breaks and normalize whitespace for display."""
    if not text:
        return ""
    cleaned = " ".join(str(text).split())
    cleaned = "".join(char for char in cleaned if ord(char) >= 32 or char in "\t\n\r")
    return cleaned


def _truncate_middle(text: str | None, max_length: int) -> str:
    """Truncate text in the middle with ellipsis to fit available space."""
    if not text or len(text) <= max_length:
        return text or ""
    half_length = (max_length - 3) // 2
    return f"{text[:half_length]}...{text[-half_length:]}"


def _variant_field(task: TaskInfo, field: str) -> str:
    """Extract a comma-separated unique set of a variant field."""
    values = sorted({getattr(v, field) for v in task.variants if getattr(v, field)})
    return ", ".join(values)


def _build_tsv_row(task: TaskInfo, key: str, prompt_text: str) -> dict:
    """Build a single TSV export row from a TaskInfo and prompt."""
    return {
        "status": task.status,
        "task_id": task.task_id,
        "database_types": _variant_field(task, "db_type"),
        "project_types": _variant_field(task, "project_type"),
        "project_name": _variant_field(task, "project_name"),
        "database_name": _variant_field(task, "db_name"),
        "key": key,
        "description": _clean_text(task.description),
        "prompt": _clean_text(prompt_text),
        "notes": _clean_text(task.notes),
        "difficulty": task.difficulty or "unknown",
        "tags": ", ".join(task.tags) if task.tags else "",
    }


@tasks_app.command()
def list(
    tasks_dir: Annotated[Path, typer.Option(help="The path to the tasks directory.")] = Path(
        "tasks"
    ),
    copy: Annotated[bool, typer.Option(help="Copy task details as TSV to clipboard")] = False,
):
    """List available tasks with their details and prompts."""
    if not tasks_dir.exists():
        typer.echo(f"Tasks directory {tasks_dir} does not exist.")
        raise typer.Exit(code=1)

    scanner = TaskScanner(tasks_dir)
    scanned_tasks = scanner.scan()

    if not scanned_tasks:
        typer.echo("No tasks found.")
        raise typer.Exit(code=0)

    console = Console()
    terminal_width = console.width
    prompt_width = max(terminal_width - 46, 40)

    table = Table(title="Available ADE-bench Tasks", expand=True)
    table.add_column("Status", style="magenta", width=6)
    table.add_column("Task ID", style="cyan", no_wrap=True, width=30)
    table.add_column("Prompt", no_wrap=True)

    all_task_data: list[dict] = []
    unique_tags: set[str] = set()
    difficulties: set[str] = set()

    for task in scanned_tasks:
        difficulties.add(task.difficulty or "unknown")
        unique_tags.update(task.tags)

        if not task.prompts:
            description = _clean_text(task.description)
            formatted_status = (
                f"[green]{task.status}[/green]" if task.status.lower() == "ready" else task.status
            )
            table.add_row(
                formatted_status,
                task.task_id,
                _truncate_middle(description, prompt_width),
            )
            all_task_data.append(_build_tsv_row(task, "", ""))
        else:
            for prompt in task.prompts:
                key = prompt.key
                prompt_text = _clean_text(prompt.prompt)
                is_base = key == "" or key.lower() == "base"

                display_task_id = task.task_id if is_base else f"{task.task_id}.{key}"

                if is_base:
                    formatted_status = (
                        f"[green]{task.status}[/green]"
                        if task.status.lower() == "ready"
                        else task.status
                    )
                else:
                    formatted_status = "[grey70]  \u21b3[/grey70]"

                table.add_row(
                    formatted_status,
                    display_task_id,
                    _truncate_middle(prompt_text, prompt_width),
                )
                all_task_data.append(_build_tsv_row(task, key, prompt.prompt))

    console.print(table)

    console.print("\n[bold]Summary:[/bold]")
    console.print(f"Total tasks: {len(scanned_tasks)}")
    console.print(f"Total rows (with prompts): {len(all_task_data)}")
    console.print(f"Difficulties: {', '.join(sorted(difficulties))}")
    console.print(f"Tags: {', '.join(sorted(unique_tags))}")

    if copy:
        _copy_to_clipboard(console, all_task_data)
    else:
        console.print("\n[dim]Tip: Use --copy to copy task details as TSV to clipboard[/dim]")


def _copy_to_clipboard(console: Console, all_task_data: list[dict]) -> None:
    """Copy task data as TSV to the system clipboard."""
    import subprocess
    import sys

    try:
        import pandas as pd
    except ImportError:
        console.print(
            "\n[red]Error: pandas required for TSV export. Install with: pip install pandas[/red]"
        )
        return

    try:
        df = pd.DataFrame(all_task_data)
        column_order = [
            "status",
            "task_id",
            "database_types",
            "project_types",
            "project_name",
            "database_name",
            "key",
            "description",
            "prompt",
            "notes",
            "difficulty",
            "tags",
        ]
        df = df[column_order]
        df = df.sort_values(["task_id", "key"])
        tsv_content = df.to_csv(index=False, sep="\t")

        copy_success = False
        if sys.platform == "darwin":
            process = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE, text=True)
            process.communicate(input=tsv_content)
            copy_success = True
        elif sys.platform.startswith("linux"):
            process = subprocess.Popen(
                ["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE, text=True
            )
            process.communicate(input=tsv_content)
            copy_success = True

        if copy_success:
            console.print("\n[green]TSV copied to clipboard[/green]")
        else:
            console.print("\n[yellow]Clipboard copy not supported on this platform[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Error copying to clipboard: {str(e)}[/red]")
