"""Interactive wizard for creating ADE-Bench tasks."""

import shutil

import click
import yaml

from ade_bench.config import config


@click.command()
def main():
    """Interactive wizard for creating new ADE-Bench tasks."""
    click.echo("Welcome to the ADE-Bench task creation wizard!")
    click.echo("This will help you create a new data analyst benchmarking task.\n")

    # Get task information
    task_id = click.prompt("Task ID (e.g., 'sales-analysis-01')")
    title = click.prompt("Task title")
    description = click.prompt("Task description", type=str)

    difficulty = click.prompt(
        "Difficulty",
        type=click.Choice(["easy", "medium", "hard"]),
        default="medium",
    )

    # Database configuration
    db_type = click.prompt(
        "Database type",
        type=click.Choice(["duckdb", "postgres", "sqlite"]),
        default="duckdb",
    )

    # Create task directory
    task_dir = config.tasks_dir / task_id

    if task_dir.exists():
        if not click.confirm(f"Task {task_id} already exists. Overwrite?"):
            click.echo("Aborted.")
            return
        shutil.rmtree(task_dir)

    task_dir.mkdir(parents=True)
    click.echo(f"\nCreated task directory: {task_dir}")

    # Create task.yaml
    task_metadata = {
        "task_id": task_id,
        "title": title,
        "description": description,
        "difficulty": difficulty,
        "tags": [],
        "test_type": "sql",
        "db_type": db_type,
    }

    with open(task_dir / "task.yaml", "w") as f:
        yaml.dump(task_metadata, f, default_flow_style=False, sort_keys=False)

    # Create directory structure
    directories = [
        "dbt_project",
        "dbt_project/models",
        "dbt_project/tests",
        "dbt_project/macros",
        "data",
        "tests",
        "expected",
    ]

    for dir_name in directories:
        (task_dir / dir_name).mkdir(exist_ok=True)

    # Create dbt_project.yml
    dbt_project_config = {
        "name": task_id.replace("-", "_"),
        "version": "1.0.0",
        "config-version": 2,
        "profile": "default",
        "model-paths": ["models"],
        "analysis-paths": ["analyses"],
        "test-paths": ["tests"],
        "seed-paths": ["seeds"],
        "macro-paths": ["macros"],
        "snapshot-paths": ["snapshots"],
        "target-path": "target",
        "clean-targets": ["target", "dbt_packages"],
        "models": {
            task_id.replace("-", "_"): {
                "materialized": "table",
            }
        },
    }

    with open(task_dir / "dbt_project" / "dbt_project.yml", "w") as f:
        yaml.dump(dbt_project_config, f, default_flow_style=False, sort_keys=False)

    # Create README template
    readme_content = f"""# {title}

## Description
{description}

## Setup
This task uses {db_type} as the database.

## Data
Place seed data files in the `data/` directory.

## Tests
SQL test queries go in the `tests/` directory.
Expected results go in the `expected/` directory as JSON files.

## Solution
Place the solution script in `solution.sh`.
"""

    with open(task_dir / "README.md", "w") as f:
        f.write(readme_content)

    # Create example files
    if click.confirm("\nCreate example files?"):
        # Example SQL test
        example_test = """-- Example test: check_row_count.sql
SELECT COUNT(*) as row_count
FROM {{ ref('my_model') }};
"""
        with open(task_dir / "tests" / "check_row_count.sql", "w") as f:
            f.write(example_test)

        # Example expected result
        example_expected = [{"row_count": 100}]
        with open(task_dir / "expected" / "check_row_count.json", "w") as f:
            import json

            json.dump(example_expected, f, indent=2)

        # Example solution
        example_solution = """#!/bin/bash
# Example solution script

# Navigate to dbt project
cd /dbt_project

# Run dbt commands
dbt deps
dbt seed
dbt run
dbt test
"""
        with open(task_dir / "solution.sh", "w") as f:
            f.write(example_solution)

        # Make solution executable
        (task_dir / "solution.sh").chmod(0o755)

    click.echo(f"\n✅ Task '{task_id}' created successfully!")
    click.echo(f"📁 Location: {task_dir}")
    click.echo("\nNext steps:")
    click.echo("1. Add seed data to the data/ directory")
    click.echo("2. Create dbt models in dbt_project/models/")
    click.echo("3. Write SQL tests in tests/")
    click.echo("4. Add expected results in expected/")
    click.echo("5. Implement the solution in solution.sh")


if __name__ == "__main__":
    main()
