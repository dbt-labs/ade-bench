#!/usr/bin/env python3
"""Generic utility to dump database relations to parquet and CSV files."""

import argparse
import json
import sys
from pathlib import Path


def dump_tables_duckdb(
    db_path: str,
    relations: list[str],
    output_dir: str,
    limit: int = -1,
    schema: str = "main",
) -> dict:
    """Dump tables from a DuckDB database to parquet + CSV.

    Args:
        db_path: Path to the .duckdb file
        relations: List of relation names to dump
        output_dir: Directory to write output files
        limit: Maximum rows per table (-1 = unlimited)
        schema: Database schema (default: main)

    Returns:
        Dict mapping relation name to status info
    """
    import duckdb

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(db_path, read_only=True)
    results = {}

    for relation in relations:
        try:
            # Check if relation exists
            exists = con.execute(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema = ? AND table_name = ?",
                [schema, relation],
            ).fetchone()[0]

            if not exists:
                print(f"[ade-bench] Warning: relation '{relation}' not found in database", flush=True)
                results[relation] = {"status": "not_found"}
                continue

            limit_clause = f"LIMIT {limit}" if limit >= 0 else ""
            query = f'SELECT * FROM "{schema}"."{relation}" {limit_clause}'

            parquet_path = output_path / f"{relation}.parquet"
            csv_path = output_path / f"{relation}.csv"

            con.execute(f"COPY ({query}) TO '{parquet_path}' (FORMAT PARQUET)")
            con.execute(f"COPY ({query}) TO '{csv_path}' (HEADER, DELIMITER ',')")

            row_count = con.execute(f'SELECT count(*) FROM "{schema}"."{relation}"').fetchone()[0]
            dumped_count = min(row_count, limit) if limit >= 0 else row_count

            print(f"[ade-bench] Dumped '{relation}': {dumped_count} rows to {parquet_path}", flush=True)
            results[relation] = {"status": "ok", "row_count": dumped_count}

        except Exception as e:
            print(f"[ade-bench] Error dumping '{relation}': {e}", flush=True)
            results[relation] = {"status": "error", "error": str(e)}

    con.close()
    return results


def dump_tables_snowflake(
    relations: list[str],
    output_dir: str,
    limit: int = -1,
    profiles_path: str = "~/.dbt/profiles.yml",
) -> dict:
    """Dump tables from Snowflake to parquet + CSV.

    Uses fetch_pandas_all() and DataFrame.to_parquet()/to_csv() directly.

    Args:
        relations: List of relation names to dump
        output_dir: Directory to write output files
        limit: Maximum rows per table (-1 = unlimited)
        profiles_path: Path to dbt profiles.yml

    Returns:
        Dict mapping relation name to status info
    """
    import yaml

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Parse Snowflake credentials from profiles.yml
    profiles_file = Path(profiles_path).expanduser()
    with open(profiles_file) as f:
        profiles = yaml.safe_load(f)

    # Find the first profile with a snowflake target
    sf_creds = None
    for profile_name, profile in profiles.items():
        if isinstance(profile, dict) and "outputs" in profile:
            target_name = profile.get("target", "dev")
            target = profile["outputs"].get(target_name, {})
            if target.get("type") == "snowflake":
                sf_creds = target
                break

    if not sf_creds:
        print("[ade-bench] Error: No Snowflake credentials found in profiles.yml", flush=True)
        return {r: {"status": "error", "error": "no credentials"} for r in relations}

    import snowflake.connector

    sf_con = snowflake.connector.connect(
        account=sf_creds["account"],
        user=sf_creds["user"],
        password=sf_creds["password"],
        database=sf_creds.get("database"),
        schema=sf_creds.get("schema"),
        warehouse=sf_creds.get("warehouse"),
        role=sf_creds.get("role"),
    )

    results = {}

    for relation in relations:
        try:
            limit_clause = f"LIMIT {limit}" if limit >= 0 else ""
            cursor = sf_con.cursor()
            cursor.execute(f'SELECT * FROM "{relation}" {limit_clause}')
            df = cursor.fetch_pandas_all()
            cursor.close()

            parquet_path = output_path / f"{relation}.parquet"
            csv_path = output_path / f"{relation}.csv"

            df.to_parquet(str(parquet_path), index=False)
            df.to_csv(str(csv_path), index=False)

            row_count = len(df)
            print(f"[ade-bench] Dumped '{relation}': {row_count} rows to {parquet_path}", flush=True)
            results[relation] = {"status": "ok", "row_count": row_count}

        except Exception as e:
            print(f"[ade-bench] Error dumping '{relation}': {e}", flush=True)
            results[relation] = {"status": "error", "error": str(e)}

    sf_con.close()
    return results


def main():
    parser = argparse.ArgumentParser(description="Dump database tables to parquet + CSV")
    parser.add_argument("--relations", nargs="+", required=True, help="Table names to dump")
    parser.add_argument("--output", required=True, help="Output directory")
    parser.add_argument("--db-type", choices=["duckdb", "snowflake"], default="duckdb")
    parser.add_argument("--db-path", help="Path to DuckDB file (for duckdb type)")
    parser.add_argument("--limit", type=int, default=-1, help="Max rows per table (-1=unlimited)")
    parser.add_argument("--profiles", default="~/.dbt/profiles.yml", help="Path to profiles.yml")
    args = parser.parse_args()

    if args.db_type == "duckdb":
        if not args.db_path:
            print("[ade-bench] Error: --db-path required for duckdb", flush=True)
            sys.exit(1)
        results = dump_tables_duckdb(args.db_path, args.relations, args.output, args.limit)
    elif args.db_type == "snowflake":
        results = dump_tables_snowflake(args.relations, args.output, args.limit, args.profiles)

    # Write results metadata
    meta_path = Path(args.output) / "dump_metadata.json"
    meta_path.write_text(json.dumps(results, indent=2))
    print(f"[ade-bench] Dump metadata written to {meta_path}", flush=True)


if __name__ == "__main__":
    main()
