#!/usr/bin/env python3
"""Fuzzy comparison of query results for ADE-Bench.

Compares an agent's result table against a gold standard CSV file,
tolerating differences in column names, column ordering, row ordering,
and minor numeric precision differences.

Columns are matched by their content (sorted values), not by name.
Extra columns in the result are tolerated. Numeric comparisons use
atol=1e-5, rtol=1e-5 tolerance.

Creates a `fuzzy_match_result` table in the DuckDB database:
  - Empty (0 rows) if comparison passes
  - Contains error details if comparison fails

Usage:
    python fuzzy_compare.py <result_table> <gold_csv_path> [--db-path <path>]
"""

import argparse
import os
import sys
from pathlib import Path

try:
    import duckdb
except ImportError:
    print("Error: duckdb is required.", file=sys.stderr)
    sys.exit(1)

try:
    import pandas as pd
except ImportError:
    print("Error: pandas is required.", file=sys.stderr)
    sys.exit(1)


def find_db_path():
    """Find the DuckDB database path from profiles.yml."""
    try:
        import yaml
        for profiles_path in ['/app/profiles.yml', '/app/profile.yml']:
            if not os.path.exists(profiles_path):
                continue
            with open(profiles_path) as f:
                profiles = yaml.safe_load(f)
            for profile_name, profile in profiles.items():
                if not isinstance(profile, dict) or 'outputs' not in profile:
                    continue
                dev = profile['outputs'].get('dev', {})
                if dev.get('type') != 'duckdb':
                    continue
                db_path = dev.get('path', 'database.duckdb')
                if not os.path.isabs(db_path):
                    db_path = os.path.join('/app', db_path)
                return db_path
    except Exception:
        pass

    # Fallback: look for any .duckdb file in /app
    for f in Path('/app').glob('*.duckdb'):
        return str(f)

    return '/app/database.duckdb'


def _is_numeric_series(series):
    """Check if a pandas Series contains numeric values."""
    if pd.api.types.is_numeric_dtype(series.dtype):
        return True
    if series.dtype == object and len(series) > 0:
        first = series.dropna().iloc[0] if series.dropna().any() else None
        if first is not None:
            return isinstance(first, (int, float, complex)) or hasattr(first, '__float__')
    return False


def match_columns(gold_df, comp_df):
    """Match gold columns to comparison columns by content.

    For each column in gold, find a column in comp with the same type
    and same sorted values. Returns a dict {comp_col: gold_col}.
    """
    mapping = {}

    for gold_col in sorted(gold_df.columns):
        gold_vals = gold_df[gold_col].sort_values().reset_index(drop=True)
        is_gold_numeric = _is_numeric_series(gold_df[gold_col])

        for comp_col in comp_df.columns:
            if comp_col in mapping:
                continue

            comp_vals = comp_df[comp_col].sort_values().reset_index(drop=True)
            is_comp_numeric = _is_numeric_series(comp_df[comp_col])

            # Check type compatibility
            types_ok = (
                gold_df[gold_col].dtype == comp_df[comp_col].dtype
                or (is_gold_numeric and is_comp_numeric)
            )
            if not types_ok:
                continue

            # Try exact match
            if gold_vals.equals(comp_vals):
                mapping[comp_col] = gold_col
                break

            # Try approximate numeric match
            if is_gold_numeric and is_comp_numeric:
                try:
                    gold_float = gold_vals.astype(float)
                    comp_float = comp_vals.astype(float)
                    pd.testing.assert_series_equal(
                        gold_float, comp_float,
                        check_dtype=False, check_names=False,
                        atol=1e-5, rtol=1e-5,
                    )
                    mapping[comp_col] = gold_col
                    break
                except (AssertionError, ValueError, TypeError):
                    pass

    mapped_gold = set(mapping.values())
    unmapped = set(gold_df.columns) - mapped_gold
    if unmapped:
        raise ValueError(
            f"Could not match gold columns: {unmapped}. "
            f"Available comparison columns: {list(comp_df.columns)}"
        )

    return mapping


def compare(gold_df, comp_df):
    """Compare two DataFrames with fuzzy matching.

    Returns (is_match: bool, error_message: str | None).
    """
    if gold_df.empty and comp_df.empty:
        return True, None

    if len(gold_df) != len(comp_df):
        return False, f"Row count mismatch: gold={len(gold_df)}, result={len(comp_df)}"

    if len(gold_df.columns) > len(comp_df.columns):
        return False, (
            f"Result has fewer columns ({len(comp_df.columns)}) "
            f"than expected ({len(gold_df.columns)})"
        )

    # Match columns by content
    try:
        col_mapping = match_columns(gold_df, comp_df)
    except ValueError as e:
        return False, str(e)

    # Rename and reorder to match gold
    comp_df = comp_df.rename(columns=col_mapping)
    cols = sorted(gold_df.columns)
    comp_df = comp_df[cols].copy()
    gold_df = gold_df.reindex(columns=cols)

    # Sort rows
    gold_df = gold_df.sort_values(by=cols).reset_index(drop=True)
    comp_df = comp_df.sort_values(by=cols).reset_index(drop=True)

    # Normalize numeric types (Decimal vs float, int vs float, etc.)
    for col in cols:
        g_numeric = _is_numeric_series(gold_df[col])
        c_numeric = _is_numeric_series(comp_df[col])
        if g_numeric and c_numeric:
            try:
                gold_df[col] = gold_df[col].astype(float)
                comp_df[col] = comp_df[col].astype(float)
            except (ValueError, TypeError):
                pass

    # Final comparison
    if gold_df.equals(comp_df):
        return True, None

    # Column-by-column check for detailed error reporting
    for col in cols:
        if gold_df[col].equals(comp_df[col]):
            continue

        if pd.api.types.is_numeric_dtype(gold_df[col]):
            try:
                pd.testing.assert_series_equal(
                    gold_df[col], comp_df[col],
                    check_dtype=False, check_names=False,
                    atol=1e-5, rtol=1e-5,
                )
                continue  # Close enough
            except AssertionError:
                pass

        diff_mask = gold_df[col] != comp_df[col]
        first_diff = diff_mask.idxmax()
        return False, (
            f"Column '{col}' differs at row {first_diff}: "
            f"gold={gold_df[col].iloc[first_diff]!r}, "
            f"result={comp_df[col].iloc[first_diff]!r}"
        )

    return True, None


def main():
    parser = argparse.ArgumentParser(description='Fuzzy comparison of query results')
    parser.add_argument('result_table', help='Name of the result table in DuckDB')
    parser.add_argument('gold_csv_path', help='Path to the gold standard CSV file')
    parser.add_argument('--db-path', help='Path to DuckDB database', default=None)
    args = parser.parse_args()

    db_path = args.db_path or find_db_path()

    conn = duckdb.connect(db_path)

    try:
        # Load gold CSV
        gold_df = pd.read_csv(args.gold_csv_path)

        # Load result table
        try:
            result_df = conn.execute(f"SELECT * FROM {args.result_table}").fetchdf()
        except Exception as e:
            error_msg = f"Could not read result table '{args.result_table}': {e}"
            conn.execute(
                "CREATE OR REPLACE TABLE fuzzy_match_result AS SELECT ? as error",
                [error_msg],
            )
            print(f"FAIL: {error_msg}", file=sys.stderr)
            return

        # Run comparison
        is_match, error_msg = compare(gold_df, result_df)

        if is_match:
            conn.execute(
                "CREATE OR REPLACE TABLE fuzzy_match_result AS SELECT 1 WHERE FALSE"
            )
            print("PASS: Results match")
        else:
            conn.execute(
                "CREATE OR REPLACE TABLE fuzzy_match_result AS SELECT ? as error",
                [error_msg],
            )
            print(f"FAIL: {error_msg}", file=sys.stderr)

    finally:
        conn.close()


if __name__ == '__main__':
    main()
