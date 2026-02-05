#!/usr/bin/env python3
"""
Script to extract task details from all task.yaml files and generate a CSV.
"""

import yaml
import pandas as pd
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Any


def clean_text_for_spreadsheet(text: str) -> str:
    """Clean text for spreadsheet compatibility."""
    if not text:
        return ""
    # Remove line breaks and normalize whitespace
    cleaned = ' '.join(text.split())
    # Remove any control characters that might cause issues
    cleaned = ''.join(char for char in cleaned if ord(char) >= 32 or char in '\t\n\r')
    return cleaned


def load_yaml_file(file_path: Path) -> Dict[str, Any]:
    """Load and parse a YAML file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        return {}


def extract_task_details(tasks_dir: Path) -> List[Dict[str, Any]]:
    """Extract details from all task.yaml files."""
    task_details = []

    # Iterate through all task directories
    for task_dir in tasks_dir.iterdir():
        if not task_dir.is_dir() or task_dir.name.startswith('.'):
            continue

        task_yaml_path = task_dir / "task.yaml"
        if not task_yaml_path.exists():
            print(f"Warning: No task.yaml found in {task_dir}")
            continue

        # Load task configuration
        task_config = load_yaml_file(task_yaml_path)
        if not task_config:
            continue

        # Extract basic task info
        task_id = clean_text_for_spreadsheet(task_config.get('task_id', ''))
        description = clean_text_for_spreadsheet(task_config.get('description', ''))
        status = clean_text_for_spreadsheet(task_config.get('status', ''))
        difficulty = clean_text_for_spreadsheet(task_config.get('difficulty', ''))
        tags = task_config.get('tags', [])

        # Extract info from variants
        variants = task_config.get('variants', [])

        db_type_list = [clean_text_for_spreadsheet(variant.get('db_type', '')) for variant in variants if variant.get('db_type')]
        db_types = ', '.join(set(db_type_list))

        project_type_list = [clean_text_for_spreadsheet(variant.get('project_type', '')) for variant in variants if variant.get('project_type')]
        project_types = ', '.join(set(project_type_list))

        database_list = [clean_text_for_spreadsheet(variant.get('db_name', '')) for variant in variants if variant.get('db_name')]
        database_name = ', '.join(set(database_list))

        project_list = [clean_text_for_spreadsheet(variant.get('project_name', '')) for variant in variants if variant.get('project_name')]
        project_name = ', '.join(set(project_list))



        # Extract prompts
        prompts = task_config.get('prompts', [])

        # Extract notes
        notes = clean_text_for_spreadsheet(task_config.get('notes', ''))

        if not prompts:
            # If no prompts, create one row with empty key and prompt
            task_details.append({
                'task_id': task_id,
                'description': description,
                'status': status,
                'database_types': db_types,
                'project_types': project_types,
                'project_name': project_name,
                'database_name': database_name,
                'key': '',
                'prompt': '',
                'notes': notes,
                'difficulty': difficulty,
                'tags': clean_text_for_spreadsheet(', '.join(tags) if tags else '')
            })
        else:
            # Create one row per prompt key
            for prompt in prompts:
                key = clean_text_for_spreadsheet(prompt.get('key', ''))
                prompt_text = clean_text_for_spreadsheet(prompt.get('prompt', ''))

                task_details.append({
                    'task_id': task_id,
                    'description': description,
                    'status': status,
                    'database_types': db_types,
                    'project_types': project_types,
                    'project_name': project_name,
                    'database_name': database_name,
                    'key': key,
                    'prompt': prompt_text,
                    'notes': notes,
                    'difficulty': difficulty,
                    'tags': clean_text_for_spreadsheet(', '.join(tags) if tags else '')
                })

    return task_details


def copy_to_clipboard(text: str) -> bool:
    """Copy text to clipboard using pbcopy (macOS) or xclip (Linux)."""
    try:
        if sys.platform == "darwin":  # macOS
            process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE, text=True)
            process.communicate(input=text)
            return True
        elif sys.platform.startswith('linux'):  # Linux
            process = subprocess.Popen(['xclip', '-selection', 'clipboard'], stdin=subprocess.PIPE, text=True)
            process.communicate(input=text)
            return True
        else:
            print("Warning: Clipboard copy not supported on this platform")
            return False
    except Exception as e:
        print(f"Warning: Failed to copy to clipboard: {e}")
        return False


def main(output_file: Path | None = None, quiet: bool = False):
    """Main function to extract task details and generate CSV.

    Args:
        output_file: Optional path to save the TSV file to
        quiet: If True, suppress verbose output
    """
    # Get the tasks directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    tasks_dir = project_root / "tasks"

    if not tasks_dir.exists():
        print(f"Error: Tasks directory not found at {tasks_dir}")
        sys.exit(1)

    if not quiet:
        print(f"Extracting task details from {tasks_dir}...")

    # Extract task details
    task_details = extract_task_details(tasks_dir)

    if not task_details:
        print("No task details found!")
        sys.exit(1)

    # Create DataFrame
    df = pd.DataFrame(task_details)

    # Reorder columns as requested
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

    # Sort by task_id and key
    df = df.sort_values(['task_id', 'key'])

    # Generate TSV for clipboard (better for Google Sheets)
    tsv_content = df.to_csv(index=False, sep='\t')

    # Save to file if output_file is provided
    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(tsv_content)
        if not quiet:
            print(f"Successfully wrote task details to {output_file}")
            print(f"  - Total tasks: {len(df['task_id'].unique())}")
            print(f"  - Total rows: {len(df)}")
        return

    # Print the CSV in a pretty format
    print("\n" + "="*80)
    print("TASK DETAILS")
    print("="*80)

    # Print header
    print(f"{'status':<8} | {'task_id':<25} | {'prompt':<60}")
    print("-" * 100)

    # Print data rows
    for _, row in df.iterrows():
        status = str(row['status'])[:7]
        task_id = str(row['task_id'])[:24]
        prompt = str(row['prompt'])[:59]
        print(f"{status:<8} | {task_id:<25} | {prompt:<60}")

    print("="*80)

    # Copy TSV to clipboard
    if copy_to_clipboard(tsv_content):
        print("✓ TSV copied to clipboard!")
    else:
        print("✗ Failed to copy to clipboard")

    # Print summary
    print("\nSummary:")
    print(f"- Total tasks: {len(df['task_id'].unique())}")
    print(f"- Total rows: {len(df)}")
    print(f"- Difficulties: {', '.join(sorted(df['difficulty'].unique()))}")

    # Get unique individual tags (split comma-separated tag strings)
    all_tags = set()
    for tags_str in df['tags'].dropna():
        if tags_str:
            tags = [tag.strip() for tag in str(tags_str).split(',')]
            all_tags.update(tags)
    print(f"- Tags: {', '.join(sorted(all_tags))}")


if __name__ == "__main__":
    main()