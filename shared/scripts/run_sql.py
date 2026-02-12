#!/usr/bin/env python3
"""
Utility script to run arbitrary SQL queries against DuckDB or Snowflake databases.

This script reads database connection details from profiles.yml and executes SQL queries
against the configured database. It can be called from setup.sh or solution.sh scripts.

Usage:
    # Read SQL from stdin
    echo "SELECT * FROM table;" | python3 /scripts/run_sql.py --db-type=duckdb

    # Read SQL from a file
    python3 /scripts/run_sql.py --db-type=snowflake --sql-file=query.sql

    # Read SQL from a here-doc in bash
    python3 /scripts/run_sql.py --db-type=duckdb << SQL
    SELECT * FROM table;
    SQL
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, Any

try:
    import yaml
except ImportError:
    print("Error: pyyaml is required. Please install it.", file=sys.stderr)
    sys.exit(1)

try:
    import duckdb
except ImportError:
    duckdb = None

try:
    import snowflake.connector

    SNOWFLAKE_AVAILABLE = True
except ImportError:
    SNOWFLAKE_AVAILABLE = False
    snowflake = None


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run SQL queries against DuckDB or Snowflake databases"
    )
    parser.add_argument(
        "--db-type",
        type=str,
        required=True,
        choices=["duckdb", "snowflake"],
        help="Database type (duckdb or snowflake)",
    )
    parser.add_argument(
        "--project-type", type=str, default="dbt", help="Project type (default: dbt)"
    )
    parser.add_argument(
        "--sql-file", type=str, help="Path to SQL file (if not provided, reads from stdin)"
    )
    parser.add_argument(
        "--profiles-path",
        type=str,
        default="/app/profiles.yml",
        help="Path to profiles.yml file (default: /app/profiles.yml)",
    )
    return parser.parse_args()


def load_profiles(profiles_path: str) -> Dict[str, Any]:
    """Load profiles.yml file."""
    path = Path(profiles_path)
    if not path.exists():
        print(f"Error: profiles.yml not found at {profiles_path}", file=sys.stderr)
        sys.exit(1)

    with open(path, "r") as f:
        return yaml.safe_load(f)


def get_profile_name(project_type: str, db_type: str, profiles: Dict[str, Any]) -> str:
    """Get the profile name from project type and db type."""
    # Try to infer project name from current directory or environment
    project_name = os.getenv("DBT_PROJECT_NAME", None)

    # Check if we're in a dbt project directory
    dbt_project_yml = Path("/app/dbt_project.yml")
    if dbt_project_yml.exists():
        with open(dbt_project_yml, "r") as f:
            dbt_config = yaml.safe_load(f)
            if "name" in dbt_config:
                project_name = dbt_config["name"]
            # Also check if profile is explicitly set
            if "profile" in dbt_config:
                profile_name = dbt_config["profile"]
                if profile_name in profiles:
                    return profile_name

    # If we still don't have a project name, try to infer from available profiles
    if not project_name:
        # Look for profiles matching the pattern {name}-{db_type}
        for profile_key in profiles.keys():
            if profile_key.endswith(f"-{db_type}"):
                return profile_key
        # If no match, return the first profile (fallback)
        if profiles:
            return list(profiles.keys())[0]
        else:
            print("Error: No profiles found in profiles.yml", file=sys.stderr)
            sys.exit(1)

    # Profile name format is typically: {project_name}-{db_type}
    profile_name = f"{project_name}-{db_type}"

    # Verify the profile exists
    if profile_name not in profiles:
        print(f"Error: Profile '{profile_name}' not found in profiles.yml", file=sys.stderr)
        print(f"Available profiles: {', '.join(profiles.keys())}", file=sys.stderr)
        sys.exit(1)

    return profile_name


def get_duckdb_connection(profiles: Dict[str, Any], profile_name: str):
    """Get DuckDB connection from profiles.yml."""
    if duckdb is None:
        print("Error: duckdb package is not available", file=sys.stderr)
        sys.exit(1)

    try:
        profile = profiles[profile_name]
        output = profile["outputs"]["dev"]
        db_path = output.get("path", "./database.duckdb")

        # Resolve relative paths relative to /app
        if not os.path.isabs(db_path):
            db_path = os.path.join("/app", db_path)

        conn = duckdb.connect(db_path)
        return conn
    except Exception as e:
        print(f"Error connecting to DuckDB: {e}", file=sys.stderr)
        sys.exit(1)


def get_snowflake_connection(profiles: Dict[str, Any], profile_name: str):
    """Get Snowflake connection from profiles.yml."""
    if not SNOWFLAKE_AVAILABLE:
        print("Error: snowflake-connector-python is not available", file=sys.stderr)
        sys.exit(1)

    try:
        profile = profiles[profile_name]
        output = profile["outputs"]["dev"]

        account = output.get("account", "")
        user = output.get("user", "")
        password = output.get("password", "")
        database = output.get("database", "")
        schema = output.get("schema", "PUBLIC")
        warehouse = output.get("warehouse", "")
        role = output.get("role", "")

        # Extract account identifier
        if ".snowflakecomputing.com" in account:
            account_id = account.replace(".snowflakecomputing.com", "")
        else:
            account_id = account

        conn = snowflake.connector.connect(
            account=account_id,
            user=user,
            password=password,
            database=database,
            schema=schema,
            warehouse=warehouse,
            role=role,
        )
        return conn
    except Exception as e:
        print(f"Error connecting to Snowflake: {e}", file=sys.stderr)
        sys.exit(1)


def read_sql(args: argparse.Namespace) -> str:
    """Read SQL from file or stdin."""
    if args.sql_file:
        sql_path = Path(args.sql_file)
        if not sql_path.exists():
            print(f"Error: SQL file not found: {args.sql_file}", file=sys.stderr)
            sys.exit(1)
        with open(sql_path, "r") as f:
            return f.read()
    else:
        # Read from stdin
        return sys.stdin.read()


def execute_sql(conn, sql: str, db_type: str) -> None:
    """Execute SQL query against the database."""
    cursor = None
    try:
        # Split SQL by semicolons to handle multiple statements
        statements = [s.strip() for s in sql.split(";") if s.strip()]

        if not statements:
            print("Error: No SQL statements found", file=sys.stderr)
            sys.exit(1)

        cursor = conn.cursor()

        for statement in statements:
            if statement:
                cursor.execute(statement)

        # For SELECT queries, fetch and print results (optional)
        # For DDL/DML, just execute
        try:
            results = cursor.fetchall()
            if results:
                # Print results if any
                for row in results:
                    print(row)
        except Exception:
            # Not a SELECT query, that's fine
            pass

        # Commit if the connection supports it
        if hasattr(conn, "commit"):
            conn.commit()

        if cursor:
            cursor.close()

    except Exception as e:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        print(f"Error executing SQL: {e}", file=sys.stderr)
        if db_type == "snowflake" and hasattr(conn, "rollback"):
            try:
                conn.rollback()
            except Exception:
                pass
        sys.exit(1)


def main():
    """Main entry point."""
    args = parse_args()

    # Load profiles
    profiles = load_profiles(args.profiles_path)

    # Get profile name
    profile_name = get_profile_name(args.project_type, args.db_type, profiles)

    # Get connection
    if args.db_type == "duckdb":
        conn = get_duckdb_connection(profiles, profile_name)
    elif args.db_type == "snowflake":
        conn = get_snowflake_connection(profiles, profile_name)
    else:
        print(f"Error: Unsupported database type: {args.db_type}", file=sys.stderr)
        sys.exit(1)

    # Read SQL
    sql = read_sql(args)

    if not sql.strip():
        print("Error: No SQL provided", file=sys.stderr)
        sys.exit(1)

    # Execute SQL
    try:
        execute_sql(conn, sql, args.db_type)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
