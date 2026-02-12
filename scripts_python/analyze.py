#!/usr/bin/env python3
"""
Analyze and merge experiment results from saved experiments.

This script:
1. Creates an output directory in dev/analysis/[output-directory]
2. Merges all .tsv files from experiments_saved into a single TSV
3. Applies migrations to normalize column structure (loaded from YAML)
4. Extracts task details and saves to output directory

Usage:
    uv run scripts_python/analyze.py -o my_analysis
    uv run scripts_python/analyze.py -o my_analysis --migration custom.yaml
"""

import argparse
import csv
from pathlib import Path
from typing import Dict, List, Any

import yaml


def load_migration_config(
    migration_file: Path | None, project_root: Path
) -> tuple[Dict[str, Dict], Dict[str, Dict[str, Dict]], Dict[str, Any]]:
    """
    Load migration configuration from a YAML file.

    Args:
        migration_file: Path to the migration YAML file (relative to migrations dir), or None for default
        project_root: Project root directory

    Returns:
        Tuple of (experiment_migrations dict, task_migrations dict, default_migration dict)
        - experiment_migrations: {experiment_id: {field: value}}
        - task_migrations: {experiment_id: {task_id: {field: value}}}
        - default_migration: {field: value}
    """
    migrations_dir = project_root / "shared" / "migrations" / "analysis"

    if migration_file is None:
        config_path = migrations_dir / "default.yaml"
    else:
        config_path = migrations_dir / migration_file

    if not config_path.exists():
        raise FileNotFoundError(f"Migration file not found: {config_path}")

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    default_migration = config.get("defaults", {})

    # Parse experiments - extract task migrations from nested 'tasks' key
    experiment_migrations = {}
    task_migrations = {}

    for exp_id, exp_config in config.get("experiments", {}).items():
        if exp_config is None:
            continue

        # Extract task-specific migrations
        if "tasks" in exp_config:
            task_migrations[exp_id] = exp_config["tasks"]

        # Everything else is experiment-level migration
        experiment_migrations[exp_id] = {k: v for k, v in exp_config.items() if k != "tasks"}

    return experiment_migrations, task_migrations, default_migration


def migrate_field(
    row: Dict[str, str],
    experiment_id: str,
    task_id: str,
    field_name: str,
    experiment_migrations: Dict[str, Dict],
    task_migrations: Dict[str, Dict[str, Dict]],
    default_migration: Dict[str, Any],
) -> str:
    """
    Apply standard migration logic for a field.

    Priority order (highest to lowest):
    1. Task-specific migration (experiment + task)
    2. Experiment-specific migration
    3. Existing value in row
    4. Default value

    Args:
        row: The row data
        experiment_id: The experiment ID
        task_id: The task ID
        field_name: The field to migrate
        experiment_migrations: Experiment-specific migration overrides
        task_migrations: Task-specific migration overrides {experiment_id: {task_id: {field: value}}}
        default_migration: Default values for missing fields
    """
    # Check for task-specific migration first (highest priority)
    if experiment_id in task_migrations:
        if task_id in task_migrations[experiment_id]:
            if field_name in task_migrations[experiment_id][task_id]:
                return str(task_migrations[experiment_id][task_id][field_name])

    # Check for experiment-specific migration
    if (
        experiment_id in experiment_migrations
        and field_name in experiment_migrations[experiment_id]
    ):
        return str(experiment_migrations[experiment_id][field_name])

    # Use existing value if present
    if field_name in row:
        return str(row[field_name])

    # Fall back to default
    return str(default_migration.get(field_name, ""))


def migrate_row(
    row: Dict[str, str],
    experiment_id: str,
    experiment_migrations: Dict[str, Dict],
    task_migrations: Dict[str, Dict[str, Dict]],
    default_migration: Dict[str, Any],
) -> Dict[str, str]:
    """
    Apply migrations to normalize a row's structure based on experiment and task config.
    """
    migrated_row = row.copy()
    task_id = row.get("task_id", "")

    # Get list of all fields that could be migrated
    fields_to_migrate = []

    # Add any fields specified in task-specific migrations for this experiment/task
    if experiment_id in task_migrations and task_id in task_migrations[experiment_id]:
        fields_to_migrate.extend(task_migrations[experiment_id][task_id].keys())

    # Add any fields specified in experiment-specific migrations
    if experiment_id in experiment_migrations:
        fields_to_migrate.extend(experiment_migrations[experiment_id].keys())

    # Deduplicate
    fields_to_migrate = list(set(fields_to_migrate))

    # Apply migrations for each field
    for field_name in fields_to_migrate:
        migrated_row[field_name] = migrate_field(
            row,
            experiment_id,
            task_id,
            field_name,
            experiment_migrations,
            task_migrations,
            default_migration,
        )

    # Remove old columns
    if "result_num" in migrated_row:
        del migrated_row["result_num"]

    return migrated_row


def get_canonical_column_order() -> List[str]:
    """
    Define the canonical column order for the merged TSV.
    """
    return [
        "experiment_id",
        "task_id",
        "result",
        "failure_type",
        "tests",
        "passed",
        "passed_percentage",
        "time_seconds",
        "cost",
        "input_tokens",
        "output_tokens",
        "cache_tokens",
        "turns",
        "agent",
        "model_name",
        "db_type",
        "project_type",
        "used_mcp",
    ]


def merge_experiment_results(
    experiments_dir: Path,
    output_file: Path,
    experiment_migrations: Dict[str, Dict],
    task_migrations: Dict[str, Dict[str, Dict]],
    default_migration: Dict[str, Any],
) -> None:
    """
    Merge all results.tsv files from saved experiments into a single TSV.

    Args:
        experiments_dir: Path to the experiments_saved directory
        output_file: Path to the output merged TSV file
        experiment_migrations: Experiment-specific migration overrides
        task_migrations: Task-specific migration overrides
        default_migration: Default values for missing fields
    """
    all_rows = []
    canonical_columns = get_canonical_column_order()

    # Find all results.tsv files in subdirectories
    tsv_files = sorted(experiments_dir.glob("*/results.tsv"))

    if not tsv_files:
        print(f"No results.tsv files found in {experiments_dir}")
        return

    print(f"Found {len(tsv_files)} experiment result files:")
    for tsv_file in tsv_files:
        print(f"  - {tsv_file.parent.name}/results.tsv")

    # Read and migrate each TSV file
    for tsv_file in tsv_files:
        experiment_id = tsv_file.parent.name
        print(f"Processing {experiment_id}...")

        with open(tsv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            rows = list(reader)

            print(f"  - Read {len(rows)} rows")

            # Apply migrations to each row with the experiment_id
            migrated_rows = [
                migrate_row(
                    row, experiment_id, experiment_migrations, task_migrations, default_migration
                )
                for row in rows
            ]
            all_rows.extend(migrated_rows)

    with open(output_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=canonical_columns, delimiter="\t", extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"Successfully wrote merged results to {output_file}")
    print(f"  - Total rows: {len(all_rows)}")


def extract_and_save_tasks(output_file: Path) -> None:
    """
    Extract task details from task.yaml files and save to TSV.
    Calls the extract_task_details script to do the work.

    Args:
        output_file: Path to the output TSV file
    """
    try:
        from extract_task_details import main as extract_main

        extract_main(output_file=output_file, quiet=False)
    except ImportError as e:
        print(f"Warning: Could not import extract_task_details: {e}")
    except Exception as e:
        print(f"Warning: Failed to extract task details: {e}")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Analyze and merge experiment results from saved experiments.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    uv run scripts_python/analyze.py -o my_analysis
    uv run scripts_python/analyze.py -o my_analysis --migration custom.yaml
    uv run scripts_python/analyze.py -o my_analysis -e experiments
        """,
    )
    parser.add_argument(
        "-o",
        "--output-directory",
        required=True,
        help="Name of output directory (will be created in dev/analysis/)",
    )
    parser.add_argument(
        "--migration",
        default=None,
        help="Migration YAML file name (in shared/migrations/analysis/). Defaults to default.yaml",
    )
    parser.add_argument(
        "-e",
        "--experiment-directory",
        default="experiments_saved",
        help="Directory containing experiment results. Defaults to experiments_saved",
    )
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    # Get project root directory (one level up from scripts_python)
    script_dir = Path(__file__).parent.resolve()
    project_root = script_dir.parent

    # Define paths
    dev_dir = project_root / "dev"
    output_dir = dev_dir / "analysis" / args.output_directory
    experiments_dir = project_root / args.experiment_directory
    merged_results_file = output_dir / "merged_results.tsv"
    tasks_file = output_dir / "tasks.tsv"

    # Step 1: Load migration configuration
    print("STARTING...")
    migration_file = args.migration
    experiment_migrations, task_migrations, default_migration = load_migration_config(
        migration_file, project_root
    )
    if migration_file:
        print(f"Loaded migration config from: {migration_file}")
    else:
        print("Loaded migration config from: default.yaml")

    # Step 2: Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {output_dir}")

    # Step 3: Merge all TSV files
    if not experiments_dir.exists():
        print(f"Error: {experiments_dir} does not exist")
        return

    merge_experiment_results(
        experiments_dir,
        merged_results_file,
        experiment_migrations,
        task_migrations,
        default_migration,
    )

    # Step 4: Extract and save task details
    extract_and_save_tasks(tasks_file)

    print(f"Merged results available at: {merged_results_file}")
    print(f"Task details available at: {tasks_file}")
    print("COMPLETE.")


if __name__ == "__main__":
    main()
