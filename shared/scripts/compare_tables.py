#!/usr/bin/env python3
"""Compare two parquet tables and produce a structured diff report."""

import argparse
import json
import sys
from pathlib import Path


def compare_tables(
    expected_path: str,
    actual_path: str,
    expected_name: str = "expected",
    actual_name: str = "actual",
    fuzzy_row_limit: int = 500,
    numeric_tolerance_pct: float = 0.01,
    numeric_tolerance_abs: float = 1e-6,
) -> dict:
    """Compare two parquet files and return a structured diff."""
    import duckdb

    con = duckdb.connect()

    # Load tables
    con.execute(f"CREATE TABLE expected AS SELECT * FROM read_parquet('{expected_path}')")
    con.execute(f"CREATE TABLE actual AS SELECT * FROM read_parquet('{actual_path}')")

    # Get column info
    expected_cols = {
        row[0].lower(): row[0]
        for row in con.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'expected'"
        ).fetchall()
    }
    actual_cols = {
        row[0].lower(): row[0]
        for row in con.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'actual'"
        ).fetchall()
    }

    missing = [expected_cols[c] for c in expected_cols if c not in actual_cols]
    extra = [actual_cols[c] for c in actual_cols if c not in expected_cols]
    shared_lower = sorted(set(expected_cols.keys()) & set(actual_cols.keys()))
    shared = [expected_cols[c] for c in shared_lower]

    expected_count = con.execute("SELECT count(*) FROM expected").fetchone()[0]
    actual_count = con.execute("SELECT count(*) FROM actual").fetchone()[0]

    result = {
        "expected_name": expected_name,
        "actual_name": actual_name,
        "expected_row_count": expected_count,
        "actual_row_count": actual_count,
        "columns": {
            "missing": missing,
            "extra": extra,
            "shared": shared,
        },
        "summary": {
            "matched_exactly": 0,
            "matched_with_diffs": 0,
            "missing_rows": 0,
            "extra_rows": 0,
        },
        "row_diffs": [],
        "missing_rows": [],
        "extra_rows": [],
    }

    if not shared:
        result["summary"]["missing_rows"] = expected_count
        result["summary"]["extra_rows"] = actual_count
        con.close()
        return result

    # Exact row matching via EXCEPT
    shared_cols_quoted = ", ".join(f'"{c}"' for c in shared)

    # Rows in expected not in actual (with synthetic row ID for fuzzy matching)
    con.execute(f"""
        CREATE TABLE missing_from_actual AS
        SELECT ROW_NUMBER() OVER () AS __ade_rn, *
        FROM (
            SELECT {shared_cols_quoted} FROM expected
            EXCEPT ALL
            SELECT {shared_cols_quoted} FROM actual
        )
    """)

    # Rows in actual not in expected
    con.execute(f"""
        CREATE TABLE extra_in_actual AS
        SELECT ROW_NUMBER() OVER () AS __ade_rn, *
        FROM (
            SELECT {shared_cols_quoted} FROM actual
            EXCEPT ALL
            SELECT {shared_cols_quoted} FROM expected
        )
    """)

    missing_count = con.execute("SELECT count(*) FROM missing_from_actual").fetchone()[0]
    extra_count = con.execute("SELECT count(*) FROM extra_in_actual").fetchone()[0]
    matched = expected_count - missing_count

    result["summary"]["matched_exactly"] = matched

    # Fuzzy matching for unmatched rows
    if missing_count > 0 and extra_count > 0:
        if missing_count <= fuzzy_row_limit and extra_count <= fuzzy_row_limit:
            fuzzy_result = _fuzzy_match_rows(
                con, shared, numeric_tolerance_pct, numeric_tolerance_abs
            )
            result["summary"]["matched_with_diffs"] = len(fuzzy_result["paired"])
            result["row_diffs"] = fuzzy_result["paired"]
            # Update missing/extra after pairing
            missing_count -= len(fuzzy_result["paired"])
            extra_count -= len(fuzzy_result["paired"])

    result["summary"]["missing_rows"] = missing_count
    result["summary"]["extra_rows"] = extra_count

    # Collect remaining unpaired rows
    result["missing_rows"] = _fetch_rows(con, "missing_from_actual", shared, 100)
    result["extra_rows"] = _fetch_rows(con, "extra_in_actual", shared, 100)

    con.close()
    return result


def _values_match(val_a, val_b, col_type: str, tol_pct: float, tol_abs: float) -> bool:
    """Check if two values match, with numeric tolerance for floats."""
    if val_a is None and val_b is None:
        return True
    if val_a is None or val_b is None:
        return False
    if col_type in ("FLOAT", "DOUBLE", "DECIMAL", "NUMERIC", "REAL") or col_type.startswith("DECIMAL"):
        try:
            a, b = float(val_a), float(val_b)
            threshold = max(abs(a) * tol_pct, tol_abs)
            return abs(a - b) <= threshold
        except (ValueError, TypeError):
            return str(val_a) == str(val_b)
    return str(val_a) == str(val_b)


def _fuzzy_match_rows(
    con, shared_cols: list[str], tol_pct: float, tol_abs: float
) -> dict:
    """Fuzzy-match unmatched rows by similarity score."""
    # Get column types
    col_types = {}
    for row in con.execute(
        "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'expected'"
    ).fetchall():
        col_types[row[0].lower()] = row[1].upper()

    shared_cols_quoted = ", ".join(f'"{c}"' for c in shared_cols)
    missing_rows = con.execute(f"SELECT __ade_rn, {shared_cols_quoted} FROM missing_from_actual").fetchall()
    extra_rows = con.execute(f"SELECT __ade_rn, {shared_cols_quoted} FROM extra_in_actual").fetchall()

    # Score each pair
    scores = []
    for mi, m_row in enumerate(missing_rows):
        for ei, e_row in enumerate(extra_rows):
            matching_cols = 0
            for ci, col in enumerate(shared_cols):
                if _values_match(
                    m_row[ci + 1], e_row[ci + 1],
                    col_types.get(col.lower(), "VARCHAR"),
                    tol_pct, tol_abs,
                ):
                    matching_cols += 1
            if matching_cols > 0:
                scores.append((matching_cols, mi, ei))

    # Greedy pairing: highest score first
    scores.sort(reverse=True)
    paired_missing = set()
    paired_extra = set()
    paired = []

    for score, mi, ei in scores:
        if mi in paired_missing or ei in paired_extra:
            continue
        paired_missing.add(mi)
        paired_extra.add(ei)

        # Build column diffs
        # Use strict equality for bucketing into identifying vs diffs.
        # Tolerance is used for:
        #   1. Similarity scoring (above) — determines which rows pair
        #   2. Annotating diffs — marks near-misses in the report
        m_row = missing_rows[mi]
        e_row = extra_rows[ei]
        diffs = {}
        identifying = {}
        for ci, col in enumerate(shared_cols):
            col_type = col_types.get(col.lower(), "VARCHAR")
            val_a, val_b = m_row[ci + 1], e_row[ci + 1]
            # Strict equality check (NULLs match NULLs)
            if (val_a is None and val_b is None) or str(val_a) == str(val_b):
                identifying[col] = str(val_a) if val_a is not None else "NULL"
            else:
                within_tol = False
                if col_type in ("FLOAT", "DOUBLE", "DECIMAL", "NUMERIC", "REAL") or col_type.startswith("DECIMAL"):
                    try:
                        a, b = float(val_a), float(val_b)
                        threshold = max(abs(a) * tol_pct, tol_abs)
                        within_tol = abs(a - b) <= threshold
                    except (ValueError, TypeError):
                        pass
                diffs[col] = {
                    "expected": str(val_a) if val_a is not None else "NULL",
                    "actual": str(val_b) if val_b is not None else "NULL",
                    "within_tolerance": within_tol,
                }

        paired.append({"identifying": identifying, "diffs": diffs})

    # Remove paired rows from unmatched tables
    if paired_missing:
        paired_missing_ids = ", ".join(str(missing_rows[mi][0]) for mi in paired_missing)
        con.execute(f"DELETE FROM missing_from_actual WHERE __ade_rn IN ({paired_missing_ids})")
    if paired_extra:
        paired_extra_ids = ", ".join(str(extra_rows[ei][0]) for ei in paired_extra)
        con.execute(f"DELETE FROM extra_in_actual WHERE __ade_rn IN ({paired_extra_ids})")

    return {"paired": paired}


def _fetch_rows(con, table: str, columns: list[str], limit: int = 100) -> list[dict]:
    """Fetch rows from a table as a list of dicts."""
    cols = ", ".join(f'"{c}"' for c in columns)
    rows = con.execute(f"SELECT {cols} FROM {table} LIMIT {limit}").fetchall()
    return [
        {col: str(val) if val is not None else "NULL" for col, val in zip(columns, row)}
        for row in rows
    ]
