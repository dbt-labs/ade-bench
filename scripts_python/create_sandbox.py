#!/usr/bin/env python3
"""
Script to create a sandbox environment from a task.
"""

import os
import sys
import shutil
import yaml
import argparse
import logging
from pathlib import Path

# Add the project root to the Python path so we can import ade_bench modules
sys.path.insert(0, str(Path(__file__).parent.parent))

def check_task_exists(task_name):
    """Check if task exists in tasks directory."""
    tasks_dir = Path("tasks")
    task_path = tasks_dir / task_name

    if not task_path.exists():
        print(f"Error: Task '{task_name}' does not exist in the tasks directory.")
        return False

    if not task_path.is_dir():
        print(f"Error: '{task_name}' exists but is not a directory.")
        return False

    return True


def wipe_sandbox_directory():
    """Wipe the contents of the sandbox directory."""
    sandbox_dir = Path("dev/sandbox")

    if not sandbox_dir.exists():
        sandbox_dir.mkdir(parents=True, exist_ok=True)
        print(f"✓ Created sandbox directory at {sandbox_dir}")
        return True

    try:
        # Remove all contents of the sandbox directory
        for item in sandbox_dir.iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)

        print(f"✓ Wiped contents of sandbox directory")
        return True
    except Exception as e:
        print(f"Error wiping sandbox directory: {e}")
        return False


def get_task_config(task_name):
    """Get the task configuration from task.yaml."""
    task_yaml_path = Path("tasks") / task_name / "task.yaml"

    if not task_yaml_path.exists():
        print(f"Error: task.yaml not found for task '{task_name}'")
        return None

    try:
        with open(task_yaml_path, 'r') as f:
            task_data = yaml.safe_load(f)

        return task_data
    except Exception as e:
        print(f"Error reading task.yaml: {e}")
        return None


def copy_item(source_path, dest_path, item_name, create_dest_dir=False):
    """Generic function to copy files or directories."""
    if not source_path.exists():
        print(f"Warning: {item_name} not found at {source_path}")
        return True

    try:
        if create_dest_dir:
            dest_path.mkdir(parents=True, exist_ok=True)

        if source_path.is_file():
            shutil.copy2(source_path, dest_path)
        elif source_path.is_dir():
            if dest_path.exists():
                # Copy contents into existing directory
                for item in source_path.iterdir():
                    if item.is_file():
                        shutil.copy2(item, dest_path)
                    elif item.is_dir():
                        shutil.copytree(item, dest_path / item.name)
            else:
                # Copy entire directory
                shutil.copytree(source_path, dest_path)

        print(f"✓ Copied {item_name} to sandbox")
        return True
    except Exception as e:
        print(f"Error copying {item_name}: {e}")
        return False


def copy_project_contents(task_name, variant):
    """Copy shared project contents to sandbox."""
    project_name = variant['project_name']
    project_type = variant['project_type']

    # Determine the project directory based on project_type
    project_type_path = 'dbt' if project_type == 'dbt-fusion' else project_type
    shared_project_dir = Path("shared/projects") / project_type_path / project_name

    if not shared_project_dir.exists():
        print(f"Error: Shared project directory '{shared_project_dir}' not found")
        return False

    sandbox_dir = Path("dev/sandbox")
    return copy_item(shared_project_dir, sandbox_dir, f"project '{project_name}'")


def find_matching_variant(task_name, db_type, project_type):
    """Find the matching variant for the given db_type and project_type."""
    task_data = get_task_config(task_name)
    if not task_data:
        return None

    # Check if variants exist
    if 'variants' not in task_data:
        print(f"Error: No variants found in task '{task_name}'")
        return None

    variants = task_data['variants']

    # Find matching variant
    for variant in variants:
        if variant.get('db_type') == db_type and variant.get('project_type') == project_type:
            return variant

    print(f"Error: No variant found for db_type='{db_type}' and project_type='{project_type}' in task '{task_name}'")
    return None


def copy_database_file(task_name, variant):
    """Copy the database file to sandbox."""
    db_name = variant['db_name']
    db_type = variant['db_type']

    # Determine the database directory based on db_type
    if db_type == 'duckdb':
        db_dir = Path("shared/databases/duckdb")
        db_file = db_dir / f"{db_name}.duckdb"
    else:
        print(f"✓ No need to copy database file for {db_type}")
        return True


    sandbox_dir = Path("dev/sandbox")
    return copy_item(db_file, sandbox_dir, f"database '{db_file.name}'")


def copy_task_files(task_name):
    """Copy various task files to sandbox."""
    task_dir = Path("tasks") / task_name
    sandbox_dir = Path("dev/sandbox")

    # Define what to copy
    items_to_copy = [
        (task_dir / "setup.sh", sandbox_dir, "setup.sh"),
        (task_dir / "solution.sh", sandbox_dir, "solution.sh"),
        (task_dir / "setup", sandbox_dir / "setup", "setup directory"),
        (task_dir / "seeds", sandbox_dir / "seeds", "seeds directory"),
        (task_dir / "tests", sandbox_dir / "tests", "tests directory"),
        (task_dir / "solutions", sandbox_dir / "solutions", "solutions directory"),
    ]

    success = True
    for source, dest, name in items_to_copy:
        if not copy_item(source, dest, name, create_dest_dir=(name.endswith("directory"))):
            success = False

    return success


def copy_migration_files(variant):
    """Copy migration files to sandbox if migration_directory is specified."""
    if 'migration_directory' not in variant:
        return True  # No migration directory specified, that's fine

    migration_dir_name = variant['migration_directory']
    migration_dir_path = Path("shared/migrations") / migration_dir_name

    if not migration_dir_path.exists():
        print(f"Warning: Migration directory '{migration_dir_path}' not found")
        return True  # Not an error, just skip migration

    sandbox_dir = Path("dev/sandbox")

    # Copy migration.sh script to sandbox root
    migration_script_path = migration_dir_path / "migration.sh"
    if migration_script_path.exists():
        if not copy_item(migration_script_path, sandbox_dir, "migration.sh script"):
            return False

    # Copy migration directory contents to sandbox/migration
    migration_dest = sandbox_dir / "migrations"
    return copy_item(migration_dir_path, migration_dest, f"migration directory '{migration_dir_name}'", create_dest_dir=True)


def copy_shared_scripts():
    """Copy shared scripts to sandbox."""
    sandbox_dir = Path("dev/sandbox")

    # Copy both seed-schema.sh and merge_yaml.py
    seed_schema_success = copy_item(
        Path("shared/scripts/seed-schema.sh"),
        sandbox_dir,
        "seed-schema.sh script"
    )
    merge_yaml_success = copy_item(
        Path("shared/scripts/merge_yaml.py"),
        sandbox_dir,
        "merge_yaml.py script"
    )

    return seed_schema_success and merge_yaml_success


def update_dbt_config(variant, task_name):
    """Update dbt_project.yml and profiles.yml files based on variant configuration."""
    sandbox_dir = Path("dev/sandbox")
    project_name = variant['project_name']
    db_type = variant['db_type']

    # Update dbt_project.yml to use the right profile
    dbt_project_path = sandbox_dir / "dbt_project.yml"
    if not dbt_project_path.exists():
        print(f"❌ dbt_project.yml not found in {sandbox_dir}")
        return False

    try:
        # Use the existing _update_project_profile function logic
        profile_name = f"{project_name}-{db_type}"

        with open(dbt_project_path, 'r') as f:
            dbt_project = yaml.safe_load(f)

        dbt_project['profile'] = profile_name

        with open(dbt_project_path, 'w') as f:
            yaml.safe_dump(dbt_project, f)

        print(f"✓ Updated dbt_project.yml to use profile: {profile_name}")

    except Exception as e:
        print(f"❌ Failed to update dbt_project.yml: {e}")
        return False

    # Update profiles.yml
    profiles_path = sandbox_dir / "profiles.yml"
    if not profiles_path.exists():
        print(f"❌ profiles.yml not found in {sandbox_dir}")
        return False

    try:
        if db_type == "snowflake":
            # Use the existing _update_snowflake_creds function logic
            from ade_bench.setup.setup_utils import generate_task_snowflake_credentials

            creds = generate_task_snowflake_credentials(task_name)

            with open(profiles_path, 'r') as f:
                profiles = yaml.safe_load(f)

            profiles[profile_name]['outputs']['dev']['account'] = creds['account'].replace('.snowflakecomputing.com', '')
            profiles[profile_name]['outputs']['dev']['user'] = creds['user']
            profiles[profile_name]['outputs']['dev']['password'] = creds['password']
            profiles[profile_name]['outputs']['dev']['role'] = creds['role']
            profiles[profile_name]['outputs']['dev']['database'] = creds['database']
            profiles[profile_name]['outputs']['dev']['schema'] = creds['schema']
            profiles[profile_name]['outputs']['dev']['warehouse'] = creds['warehouse']

            with open(profiles_path, 'w') as f:
                yaml.safe_dump(profiles, f)

            print(f"✓ Updated profiles.yml with generated Snowflake credentials for {profile_name}")

        elif db_type == "duckdb":
            # For DuckDB, just ensure the path is correct
            with open(profiles_path, 'r') as f:
                profiles = yaml.safe_load(f)

            profiles[profile_name]['outputs']['dev']['path'] = f"./{variant['db_name']}.duckdb"

            with open(profiles_path, 'w') as f:
                yaml.safe_dump(profiles, f)

            print(f"✓ Updated profiles.yml for DuckDB path: {profile_name}")

    except Exception as e:
        print(f"❌ Failed to update profiles.yml: {e}")
        return False

    return True


def main():
    parser = argparse.ArgumentParser(description="Create a sandbox environment from a task")
    parser.add_argument("--task", help="Name of the task to create sandbox for")
    parser.add_argument("--db", required=True, help="Database type (duckdb, sqlite, postgres, snowflake)")
    parser.add_argument("--project-type", required=True, help="Project type (dbt, other)")

    args = parser.parse_args()

    task_name = args.task
    db_type = args.db
    project_type = args.project_type

    print(f"Creating sandbox for task: {task_name}")
    print(f"Database type: {db_type}")
    print(f"Project type: {project_type}")
    print("-" * 50)

    # Step 1: Check if task exists
    if not check_task_exists(task_name):
        sys.exit(1)

    print(f"✓ Task '{task_name}' found")

    # Step 2: Find matching variant
    variant = find_matching_variant(task_name, db_type, project_type)
    if not variant:
        sys.exit(1)

    print(f"✓ Found matching variant: db_name='{variant['db_name']}', project_name='{variant['project_name']}'")
    if 'migration_directory' in variant:
        print(f"✓ Migration directory: {variant['migration_directory']}")

    # Step 3: Wipe sandbox directory
    if not wipe_sandbox_directory():
        sys.exit(1)

    # Step 4: Copy shared project contents
    if not copy_project_contents(task_name, variant):
        sys.exit(1)

    # Step 5: Copy database file
    if not copy_database_file(task_name, variant):
        sys.exit(1)

    # Step 6: Copy migration files (if specified)
    if not copy_migration_files(variant):
        sys.exit(1)

    # Step 7: Copy task files (scripts, seeds, tests)
    if not copy_task_files(task_name):
        sys.exit(1)

    # Step 8: Copy shared scripts
    if not copy_shared_scripts():
        sys.exit(1)

    # Step 9: Update dbt configuration files
    print(f"✓ Updating dbt configuration files...")
    if not update_dbt_config(variant, task_name):
        print(f"❌ Failed to update dbt configuration files")
        sys.exit(1)

    print("-" * 50)
    print(f"✓ Sandbox created successfully for task '{task_name}'!")
    print(f"✓ Using variant: {db_type}/{variant['db_name']} + {project_type}/{variant['project_name']}")

    # Get the absolute path to the sandbox directory
    sandbox_dir = Path("dev/sandbox").absolute()
    print(f"Sandbox location: {sandbox_dir}")
    print(f"\nTo change to the sandbox directory, run:")
    print(f"cd {sandbox_dir}")


if __name__ == "__main__":
    main()