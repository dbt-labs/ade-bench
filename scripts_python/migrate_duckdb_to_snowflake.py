#!/usr/bin/env python3
"""
DuckDB to Snowflake migration script.

This script:
1. Discovers DuckDB files in specified directories
2. Analyzes schemas and tables in each DuckDB file
3. Creates Snowflake databases with the same name as DuckDB files
4. Loads data from DuckDB to Snowflake via Parquet files

Usage:
    # Run from outside the project directory to avoid module conflicts
    cd /tmp
    python /path/to/scripts_python/migrate_duckdb_to_snowflake.py [options]

Requirements:
    - pip install snowflake-connector-python duckdb pandas pyarrow
    - Snowflake account with appropriate permissions
    - Note: Run from outside project directory due to local 'docker' folder conflict
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

try:
    import snowflake.connector

    SNOWFLAKE_AVAILABLE = True
except ImportError:
    SNOWFLAKE_AVAILABLE = False
    snowflake = None

try:
    from .duckdb_utils import DuckDBExtractor
except ImportError:
    from duckdb_utils import DuckDBExtractor

# Configuration - modify these paths as needed
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNOWFLAKE_OUTPUT_DIR = os.path.join(PROJECT_ROOT, "shared", "databases", "snowflake")


class DuckDBToSnowflakeConverter:
    """Main converter class that handles the entire conversion pipeline."""

    def __init__(self):
        self.output_dir = Path(SNOWFLAKE_OUTPUT_DIR).resolve()
        self.duckdb_extractor = DuckDBExtractor()
        self.snowflake_conn = None

        # Create output directory structure
        self.output_dir.mkdir(exist_ok=True)

    def _execute_queries(self, cursor, queries: str, description: str = ""):
        """Execute multiple SQL queries separated by semicolons."""
        for query in queries.split(";"):
            query = query.strip()
            if query:
                # print(f"  - {query}")
                cursor.execute(query)

    def add_exclusions(self, exclusion_list: List[str]):
        """Add files to exclusion list."""
        self.duckdb_extractor.add_exclusions(exclusion_list)

    def discover_duckdb_files(self, patterns: List[str] = None) -> List[Path]:
        """Discover DuckDB files in the configured source directory."""
        return self.duckdb_extractor.discover_duckdb_files(patterns)

    def analyze_duckdb_schema(self, db_path: Path) -> Dict:
        """Analyze schema and tables in a DuckDB file."""
        return self.duckdb_extractor.analyze_duckdb_schema(db_path)

    def should_exclude_file(self, db_path: Path) -> bool:
        """Check if file should be excluded from conversion."""
        return self.duckdb_extractor.should_exclude_file(db_path)

    def should_include_file(self, db_path: Path, include_list: List[str]) -> bool:
        """Check if file should be included in conversion."""
        return self.duckdb_extractor.should_include_file(db_path, include_list)

    def get_snowflake_connection(self):
        """Get Snowflake connection using environment variables."""
        if not SNOWFLAKE_AVAILABLE:
            raise RuntimeError(
                "Snowflake connector not available. Please install snowflake-connector-python."
            )

        # Get Snowflake credentials from environment
        account = os.getenv("SNOWFLAKE_ACCOUNT")
        user = os.getenv("SNOWFLAKE_USER")
        password = os.getenv("SNOWFLAKE_PASSWORD")

        if not all([account, user, password]):
            raise ValueError(
                "Missing required Snowflake credentials. Please set SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, and SNOWFLAKE_PASSWORD environment variables."
            )

        # Extract account identifier
        if ".snowflakecomputing.com" in account:
            account_id = account.replace(".snowflakecomputing.com", "")
        else:
            account_id = account

        conn = snowflake.connector.connect(account=account_id, user=user, password=password)

        return conn

    def create_snowflake_database(self, db_name: str) -> bool:
        """Create or replace a Snowflake database."""
        try:
            with self.get_snowflake_connection() as conn:
                cursor = conn.cursor()

                # Drop database if it exists, then create it
                create_db_query = f"""
                    DROP DATABASE IF EXISTS {db_name};
                    CREATE DATABASE {db_name};
                    USE DATABASE {db_name};
                """
                self._execute_queries(cursor, create_db_query)

                print(f"  ✅ Created/replaced database: {db_name}")

                return True

        except Exception as e:
            print(f"  ❌ Error creating database {db_name}: {e}", file=sys.stderr)
            return False

    def load_parquet_to_snowflake(
        self, parquet_path: Path, db_name: str, schema_name: str, table_name: str
    ) -> bool:
        """Load a Parquet file into Snowflake using internal stage and COPY INTO."""
        try:
            with self.get_snowflake_connection() as conn:
                cursor = conn.cursor()

                # Use the target database and schema
                cursor.execute(f"USE DATABASE {db_name}")
                cursor.execute(f"USE SCHEMA {schema_name}")

                # Create a temporary internal stage for this table
                stage_name = f"temp_stage_{table_name.lower()}"
                file_format_name = f"temp_parquet_format_{table_name.lower()}"

                # Create file format and stage
                create_file_format_query = f"CREATE OR REPLACE FILE FORMAT {file_format_name} TYPE = PARQUET USE_LOGICAL_TYPE = TRUE;"
                cursor.execute(create_file_format_query)

                create_stage_query = (
                    f"CREATE OR REPLACE STAGE {stage_name} FILE_FORMAT={file_format_name};"
                )
                cursor.execute(create_stage_query)

                # Upload the Parquet file to the stage
                put_query = (
                    f"PUT file://{parquet_path} @{stage_name} AUTO_COMPRESS=FALSE OVERWRITE=TRUE;"
                )
                cursor.execute(put_query)

                # Create table using Snowflake's schema inference from Parquet
                create_table_query = f"""
                CREATE OR REPLACE TABLE {table_name}
                USING TEMPLATE (
                    SELECT ARRAY_AGG(OBJECT_CONSTRUCT(*))
                    FROM TABLE(
                        INFER_SCHEMA(
                            LOCATION=>'@{stage_name}/{parquet_path.name}',
                            FILE_FORMAT=>'{file_format_name}',
                            IGNORE_CASE => TRUE
                        )
                    )
                );
                """
                cursor.execute(create_table_query)

                # Load data from stage into table using COPY INTO
                copy_query = f"""
                COPY INTO {table_name}
                FROM @{stage_name}/{parquet_path.name}
                FILE_FORMAT=(FORMAT_NAME='{file_format_name}')
                MATCH_BY_COLUMN_NAME=CASE_INSENSITIVE
                ON_ERROR=CONTINUE
                """
                cursor.execute(copy_query)

                # Verify data was loaded
                count_query = f"SELECT COUNT(*) FROM {table_name}"
                cursor.execute(count_query)
                count = cursor.fetchone()[0]
                print(f"    ✅ Loaded {count} rows into {table_name}")

                # Clean up stage and file format
                cursor.execute(f"DROP STAGE IF EXISTS {stage_name}")
                cursor.execute(f"DROP FILE FORMAT IF EXISTS {file_format_name}")

                return True

        except Exception as e:
            print(f"    ❌ Error loading {table_name} to Snowflake: {e}", file=sys.stderr)
            return False

    def _extract_table_name(self, parquet_filename: str) -> str:
        """Extract table name from Parquet filename."""
        # For database export: just the filename without extension
        # For individual table export: {db_name}_main_{table_name}.parquet
        name_without_ext = parquet_filename.replace(".parquet", "")

        # Check if it's the old format with underscores and 'main'
        parts = name_without_ext.split("_")
        try:
            main_index = parts.index("main")
            if main_index + 1 < len(parts):
                # Return everything after 'main'
                return "_".join(parts[main_index + 1 :])
        except ValueError:
            pass

        # For database export format, just use the filename without extension
        return name_without_ext

    def convert_duckdb_to_snowflake(
        self, duckdb_path: Path, db_name: str = None, use_database_export: bool = False
    ) -> Optional[Dict]:
        """Convert a DuckDB file to Snowflake database."""
        if db_name is None:
            db_name = duckdb_path.stem

        print(f"Converting {duckdb_path.name} to Snowflake database '{db_name}'...")

        # Analyze the DuckDB file first
        analysis = self.analyze_duckdb_schema(duckdb_path)
        if "error" in analysis:
            print(f"Error analyzing {duckdb_path.name}: {analysis['error']}", file=sys.stderr)
            return None

        if analysis["total_tables"] == 0:
            print(f"No tables found in {duckdb_path.name}, skipping...", file=sys.stderr)
            return None

        results = {
            "database": db_name,
            "duckdb_file": str(duckdb_path),
            "tables_exported": 0,
            "tables_loaded": 0,
            "errors": [],
        }

        try:
            # Create Snowflake database
            if not self.create_snowflake_database(db_name):
                results["errors"].append("Failed to create database")
                return results

            # Create database-specific directory for Parquet files
            db_parquet_dir = self.output_dir / db_name
            db_parquet_dir.mkdir(exist_ok=True)

            # Export all tables to Parquet using shared utility
            if use_database_export:
                # Use the more efficient database export
                parquet_results = self.duckdb_extractor.export_database_to_parquet(
                    duckdb_path, self.output_dir, db_name
                )
            else:
                # Use individual table export (original method)
                parquet_results = self.duckdb_extractor.export_all_tables_to_parquet(
                    duckdb_path, db_parquet_dir, db_name
                )

            if not parquet_results["success"]:
                results["errors"].append(parquet_results["error"])
                return results

            results["tables_exported"] = parquet_results["tables_exported"]

            # Load each Parquet file to Snowflake
            for parquet_info in parquet_results["parquet_files"]:
                schema_name = parquet_info["schema"]
                parquet_path = Path(parquet_info["file_path"])

                # Extract table name from Parquet filename
                table_name = self._extract_table_name(parquet_path.name)

                print(f"    Loading {table_name} to Snowflake...")

                target_schema = "PUBLIC" if schema_name == "main" else schema_name
                if self.load_parquet_to_snowflake(parquet_path, db_name, target_schema, table_name):
                    results["tables_loaded"] += 1

            return results

        except Exception as e:
            print(f"Error converting {duckdb_path.name}: {e}", file=sys.stderr)
            results["errors"].append(str(e))
            return results

    def convert_all(
        self,
        exclusion_list: List[str] = None,
        include_list: List[str] = None,
        use_database_export: bool = False,
    ) -> Dict:
        """Convert all discovered DuckDB files to Snowflake databases."""
        if exclusion_list:
            self.add_exclusions(exclusion_list)

        # Discover DuckDB files
        print(f"Discovering DuckDB files in {self.duckdb_extractor.source_dir}...")
        duckdb_files = self.discover_duckdb_files()
        print(f"Found {len(duckdb_files)} DuckDB files")

        # Filter files based on include/exclude logic
        filtered_files = self.duckdb_extractor.filter_files(duckdb_files, include_list)
        excluded_count = len(duckdb_files) - len(filtered_files)
        if excluded_count > 0:
            print(f"Excluded {excluded_count} files based on exclusion list")

        print(f"Processing {len(filtered_files)} files...")

        results = {
            "converted": [],
            "failed": [],
            "skipped": [],
            "total_discovered": len(duckdb_files),
            "total_processed": len(filtered_files),
        }

        # Process each file
        for i, duckdb_path in enumerate(filtered_files, 1):
            print(f"\n[{i}/{len(filtered_files)}] Processing {duckdb_path.name}...")

            # Convert to Snowflake
            conversion_result = self.convert_duckdb_to_snowflake(
                duckdb_path, use_database_export=use_database_export
            )

            if conversion_result is None or conversion_result.get("errors"):
                results["failed"].append(
                    {
                        "duckdb_file": str(duckdb_path),
                        "errors": (
                            conversion_result.get("errors", ["Unknown error"])
                            if conversion_result
                            else ["Conversion failed"]
                        ),
                    }
                )
                continue

            results["converted"].append(conversion_result)

        return results


def main(include: List[str] = None, exclude: List[str] = None, use_database_export: bool = False):
    # If called from command line with no parameters, use argparse
    if include is None and exclude is None and use_database_export is False and len(sys.argv) > 1:
        parser = argparse.ArgumentParser(add_help=False)

        parser.add_argument("--exclude", nargs="*", default=[])

        parser.add_argument("--include", nargs="*", default=[])

        parser.add_argument(
            "--use-database-export",
            action="store_true",
            help="Use DuckDB's EXPORT DATABASE command for more efficient export (default: use individual table export)",
        )

        args = parser.parse_args()
        include = args.include
        exclude = args.exclude
        use_database_export = args.use_database_export

    # Convert None to empty list
    include = include or []
    exclude = exclude or []

    # Check if Snowflake is available
    if not SNOWFLAKE_AVAILABLE:
        print(
            "Error: Snowflake connector not available. Please install snowflake-connector-python.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Create converter
    converter = DuckDBToSnowflakeConverter()

    # Perform conversion
    try:
        results = converter.convert_all(exclude, include, use_database_export)

        # Print summary
        print(f"\n{'='*60}")
        print("CONVERSION SUMMARY")
        print(f"{'='*60}")
        print(f"Total DuckDB files discovered: {results['total_discovered']}")
        print(f"Total DuckDB files processed: {results['total_processed']}")
        print(f"Successfully converted: {len(results['converted'])}")
        print(f"Failed: {len(results['failed'])}")

        if results["converted"]:
            print("\nSuccessfully converted:")
            for item in results["converted"]:
                print(
                    f"  ✅ {item['database']} ({item['tables_exported']} tables exported, {item['tables_loaded']} loaded)"
                )

        if results["failed"]:
            print("\nFailed conversions:")
            for item in results["failed"]:
                print(f"  ❌ {Path(item['duckdb_file']).name}: {', '.join(item['errors'])}")

    except KeyboardInterrupt:
        print("\nConversion interrupted by user", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Conversion failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
