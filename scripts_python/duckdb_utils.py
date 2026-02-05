#!/usr/bin/env python3
"""
Shared DuckDB utilities for data extraction and analysis.

This module provides common functionality for extracting data from DuckDB files,
including schema analysis, file discovery, and data export capabilities.
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Set
import duckdb


class DuckDBExtractor:
    """Shared utilities for DuckDB data extraction and analysis."""

    def __init__(self, source_dir: str = None):
        """
        Initialize the DuckDB extractor.

        Args:
            source_dir: Path to directory containing DuckDB files. If None, uses default.
        """
        if source_dir is None:
            # Default to shared/databases/duckdb relative to this script
            script_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(script_dir)
            source_dir = os.path.join(project_root, "shared", "databases", "duckdb")

        self.source_dir = Path(source_dir).resolve()
        self.excluded_files: Set[str] = set()

    def add_exclusions(self, exclusion_list: List[str]):
        """Add files to exclusion list."""
        self.excluded_files.update(exclusion_list)

    def discover_duckdb_files(self, patterns: List[str] = None) -> List[Path]:
        """Discover DuckDB files in the configured source directory."""
        if patterns is None:
            patterns = ["*.duckdb", "*.db", "*.ddb"]

        if not self.source_dir.exists():
            print(f"Error: Source directory does not exist: {self.source_dir}", file=sys.stderr)
            return []

        discovered_files = []
        for pattern in patterns:
            discovered_files.extend(self.source_dir.glob(pattern))

        # Remove duplicates and sort
        return sorted(set(discovered_files))

    def analyze_duckdb_schema(self, db_path: Path) -> Dict:
        """Analyze schema and tables in a DuckDB file."""
        try:
            with duckdb.connect(str(db_path), read_only=True) as conn:
                # Get all schemas
                schemas = conn.execute(
                    """
                    SELECT schema_name
                    FROM information_schema.schemata
                    WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
                    ORDER BY schema_name
                """
                ).fetchall()

                schema_info = {}
                for (schema_name,) in schemas:
                    # Get tables in this schema
                    tables = conn.execute(
                        """
                        SELECT table_name, table_type
                        FROM information_schema.tables
                        WHERE table_schema = ? AND table_type = 'BASE TABLE'
                        ORDER BY table_name
                    """,
                        [schema_name],
                    ).fetchall()

                    if tables:
                        schema_info[schema_name] = {
                            "tables": [{"name": name, "type": ttype} for name, ttype in tables],
                            "table_count": len(tables),
                        }

                return {
                    "file_path": str(db_path),
                    "file_name": db_path.name,
                    "schemas": schema_info,
                    "total_tables": sum(info["table_count"] for info in schema_info.values()),
                }

        except Exception as e:
            return {
                "file_path": str(db_path),
                "file_name": db_path.name,
                "error": str(e),
                "schemas": {},
                "total_tables": 0,
            }

    def should_exclude_file(self, db_path: Path) -> bool:
        """Check if file should be excluded from processing."""
        file_name = db_path.name
        file_stem = db_path.stem

        # Check exact filename and stem
        if file_name in self.excluded_files or file_stem in self.excluded_files:
            return True

        # Check if any exclusion pattern matches
        for exclusion in self.excluded_files:
            if exclusion in file_name or exclusion in file_stem:
                return True

        return False

    def should_include_file(self, db_path: Path, include_list: List[str]) -> bool:
        """Check if file should be included in processing."""
        if not include_list:
            return True  # If no include list, include all

        file_name = db_path.name
        file_stem = db_path.stem

        # Check exact filename and stem
        if file_name in include_list or file_stem in include_list:
            return True

        # Check if any include pattern matches
        for include_pattern in include_list:
            if include_pattern in file_name or include_pattern in file_stem:
                return True

        return False

    def export_table_to_parquet(
        self, duckdb_path: Path, schema_name: str, table_name: str, output_path: Path
    ) -> bool:
        """Export a single table from DuckDB to Parquet format using direct DuckDB export."""
        try:
            with duckdb.connect(str(duckdb_path), read_only=True) as conn:
                # First check if table is empty
                if schema_name == "main":
                    count_query = f'SELECT COUNT(*) FROM "{table_name}"'
                else:
                    count_query = f'SELECT COUNT(*) FROM {schema_name}."{table_name}"'

                row_count = conn.execute(count_query).fetchone()[0]

                # Use DuckDB's direct export to Parquet
                if schema_name == "main":
                    export_query = f'COPY (SELECT * FROM "{table_name}") TO "{output_path}" (FORMAT PARQUET, COMPRESSION ZSTD)'
                else:
                    export_query = f'COPY (SELECT * FROM {schema_name}."{table_name}") TO "{output_path}" (FORMAT PARQUET, COMPRESSION ZSTD)'

                conn.execute(export_query)

                print(f"    ✅ Exported {table_name} ({row_count} rows) -> {output_path.name}")
                return True

        except Exception as e:
            print(f"    ❌ Error exporting {table_name}: {e}", file=sys.stderr)
            return False

    def export_all_tables_to_parquet(
        self, duckdb_path: Path, output_dir: Path, db_name: str = None
    ) -> Dict:
        """
        Export all tables from a DuckDB file to Parquet format.

        Args:
            duckdb_path: Path to the DuckDB file
            output_dir: Directory to write Parquet files
            db_name: Name for the database (used in file naming)

        Returns:
            Dictionary with export results
        """
        if db_name is None:
            db_name = duckdb_path.stem

        # Analyze the DuckDB file first
        analysis = self.analyze_duckdb_schema(duckdb_path)
        if "error" in analysis:
            return {
                "success": False,
                "error": analysis["error"],
                "tables_exported": 0,
                "parquet_files": [],
            }

        if analysis["total_tables"] == 0:
            return {
                "success": False,
                "error": "No tables found",
                "tables_exported": 0,
                "parquet_files": [],
            }

        results = {"success": True, "tables_exported": 0, "parquet_files": [], "errors": []}

        # Export each table to Parquet
        for schema_name, schema_info in analysis["schemas"].items():
            print(
                f"  Processing schema '{schema_name}' with {schema_info['table_count']} tables..."
            )

            for table_info in schema_info["tables"]:
                table_name = table_info["name"]
                print(f"    Processing table: {table_name}")

                # Create parquet file path
                parquet_filename = f"{db_name}_{schema_name}_{table_name}.parquet"
                parquet_path = output_dir / parquet_filename

                # Export to Parquet
                if self.export_table_to_parquet(duckdb_path, schema_name, table_name, parquet_path):
                    results["tables_exported"] += 1
                    results["parquet_files"].append(
                        {
                            "schema": schema_name,
                            "table": table_name,
                            "file_path": str(parquet_path),
                            "filename": parquet_filename,
                        }
                    )
                else:
                    results["errors"].append(f"Failed to export {schema_name}.{table_name}")

        return results

    def export_database_to_parquet(
        self, duckdb_path: Path, output_dir: Path, db_name: str = None
    ) -> Dict:
        """
        Export entire DuckDB database to Parquet using DuckDB's EXPORT DATABASE command.
        This is more efficient than exporting tables individually.

        Args:
            duckdb_path: Path to the DuckDB file
            output_dir: Directory to write Parquet files
            db_name: Name for the database (used in file naming)

        Returns:
            Dictionary with export results
        """
        if db_name is None:
            db_name = duckdb_path.stem

        try:
            with duckdb.connect(str(duckdb_path), read_only=True) as conn:
                # Create database-specific subdirectory
                db_parquet_dir = output_dir / db_name
                db_parquet_dir.mkdir(exist_ok=True)

                # Use DuckDB's EXPORT DATABASE command
                export_query = (
                    f"EXPORT DATABASE '{db_parquet_dir}' (FORMAT PARQUET, COMPRESSION ZSTD);"
                )
                print(f"  Exporting entire database using: {export_query}")
                conn.execute(export_query)

                # Count exported files
                parquet_files = list(db_parquet_dir.glob("**/*.parquet"))

                print(f"  ✅ Exported {len(parquet_files)} Parquet files to {db_parquet_dir}")

                return {
                    "success": True,
                    "tables_exported": len(parquet_files),
                    "parquet_files": [
                        {
                            "schema": "main",  # DuckDB export doesn't preserve schema info easily
                            "table": f.stem,
                            "file_path": str(f),
                            "filename": f.name,
                        }
                        for f in parquet_files
                    ],
                    "errors": [],
                }

        except Exception as e:
            print(f"  ❌ Error exporting database: {e}", file=sys.stderr)
            return {"success": False, "error": str(e), "tables_exported": 0, "parquet_files": []}

    def filter_files(self, files: List[Path], include_list: List[str] = None) -> List[Path]:
        """Filter files based on include/exclude logic."""
        if include_list:
            # If include list is specified, only include those files
            filtered_files = [f for f in files if self.should_include_file(f, include_list)]
        else:
            # If no include list, exclude based on exclusion list
            filtered_files = [f for f in files if not self.should_exclude_file(f)]

        return filtered_files
