#!/usr/bin/env python3
"""Compare two parquet tables and produce a structured diff report."""

import argparse
import sys
from pathlib import Path


def compare_tables(
    expected_path: str,
    actual_path: str,
    expected_name: str = "expected",
    actual_name: str = "actual",
    fuzzy_row_limit: int = 10000,
    numeric_tolerance_pct: float = 0.01,
    numeric_tolerance_abs: float = 1e-6,
) -> dict:
    """Compare two parquet files and return a structured diff."""
    import duckdb

    con = duckdb.connect()
    try:
        return _compare_tables_inner(
            con,
            expected_path,
            actual_path,
            expected_name,
            actual_name,
            fuzzy_row_limit,
            numeric_tolerance_pct,
            numeric_tolerance_abs,
        )
    finally:
        con.close()


def _compare_tables_inner(
    con,
    expected_path: str,
    actual_path: str,
    expected_name: str,
    actual_name: str,
    fuzzy_row_limit: int,
    numeric_tolerance_pct: float,
    numeric_tolerance_abs: float,
) -> dict:
    """Inner comparison logic operating on an open DuckDB connection."""
    # Load tables — use parameterized read_parquet to avoid path injection
    con.execute("CREATE TABLE expected AS SELECT * FROM read_parquet(?)", [expected_path])
    con.execute("CREATE TABLE actual AS SELECT * FROM read_parquet(?)", [actual_path])

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

    # Pre-scan for systematic columns: when most rows fail EXCEPT ALL,
    # check if excluding individual columns recovers matches.
    pre_systematic = {}
    if matched == 0 and expected_count > 0 and expected_count == actual_count and len(shared) >= 2:
        pre_systematic = _detect_systematic_columns(con, shared, expected_count)

    # If systematic columns found, redo EXCEPT ALL without them
    if pre_systematic:
        non_sys_cols = [c for c in shared if c not in pre_systematic]
        non_sys_quoted = ", ".join(f'"{c}"' for c in non_sys_cols)

        con.execute("DROP TABLE IF EXISTS missing_from_actual")
        con.execute("DROP TABLE IF EXISTS extra_in_actual")
        con.execute(f"""
            CREATE TABLE missing_from_actual AS
            SELECT ROW_NUMBER() OVER () AS __ade_rn, *
            FROM (
                SELECT {non_sys_quoted} FROM expected
                EXCEPT ALL
                SELECT {non_sys_quoted} FROM actual
            )
        """)
        con.execute(f"""
            CREATE TABLE extra_in_actual AS
            SELECT ROW_NUMBER() OVER () AS __ade_rn, *
            FROM (
                SELECT {non_sys_quoted} FROM actual
                EXCEPT ALL
                SELECT {non_sys_quoted} FROM expected
            )
        """)
        missing_count = con.execute("SELECT count(*) FROM missing_from_actual").fetchone()[0]
        extra_count = con.execute("SELECT count(*) FROM extra_in_actual").fetchone()[0]
        matched = expected_count - missing_count

    result["summary"]["matched_exactly"] = matched

    # Columns available in the unmatched tables (excludes pre-systematic cols)
    active_cols = [c for c in shared if c not in pre_systematic] if pre_systematic else shared

    # Fuzzy matching for unmatched rows
    if missing_count > 0 and extra_count > 0:
        if missing_count <= fuzzy_row_limit and extra_count <= fuzzy_row_limit:
            fuzzy_result = _fuzzy_match_rows(
                con, active_cols, numeric_tolerance_pct, numeric_tolerance_abs
            )
            result["summary"]["matched_with_diffs"] = len(fuzzy_result["paired"])
            result["row_diffs"] = fuzzy_result["paired"]
            # Update missing/extra after pairing
            missing_count -= len(fuzzy_result["paired"])
            extra_count -= len(fuzzy_result["paired"])

    result["summary"]["missing_rows"] = missing_count
    result["summary"]["extra_rows"] = extra_count

    # Detect systematic diffs from two sources:
    # 1. Pre-scan column exclusion (works even when fuzzy matching is skipped)
    # 2. Post-fuzzy per-row analysis (catches diffs in remaining paired rows)
    result["systematic_diffs"] = dict(pre_systematic)
    if result["row_diffs"]:
        post_systematic = _detect_systematic_diffs(result["row_diffs"])
        result["systematic_diffs"].update(post_systematic)
        # Strip systematic columns from individual row diffs
        if result["systematic_diffs"]:
            sys_cols = set(result["systematic_diffs"].keys())
            cleaned = []
            for diff in result["row_diffs"]:
                remaining_diffs = {k: v for k, v in diff["diffs"].items() if k not in sys_cols}
                cleaned.append(
                    {
                        "identifying": diff["identifying"],
                        "diffs": remaining_diffs,
                    }
                )
            result["row_diffs"] = cleaned

    # Collect remaining unpaired rows
    result["missing_rows"] = _fetch_rows(con, "missing_from_actual", active_cols, 100)
    result["extra_rows"] = _fetch_rows(con, "extra_in_actual", active_cols, 100)

    return result


def _values_match(val_a, val_b, col_type: str, tol_pct: float, tol_abs: float) -> bool:
    """Check if two values match, with numeric tolerance for floats."""
    if val_a is None and val_b is None:
        return True
    if val_a is None or val_b is None:
        return False
    if col_type in ("FLOAT", "DOUBLE", "DECIMAL", "NUMERIC", "REAL") or col_type.startswith(
        "DECIMAL"
    ):
        try:
            a, b = float(val_a), float(val_b)
            threshold = max(abs(a) * tol_pct, tol_abs)
            return abs(a - b) <= threshold
        except (ValueError, TypeError):
            return str(val_a) == str(val_b)
    return str(val_a) == str(val_b)


def _fuzzy_match_rows(con, shared_cols: list[str], tol_pct: float, tol_abs: float) -> dict:
    """Fuzzy-match unmatched rows by similarity score."""
    # Get column types
    col_types = {}
    for row in con.execute(
        "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'expected'"
    ).fetchall():
        col_types[row[0].lower()] = row[1].upper()

    shared_cols_quoted = ", ".join(f'"{c}"' for c in shared_cols)
    missing_rows = con.execute(
        f"SELECT __ade_rn, {shared_cols_quoted} FROM missing_from_actual"
    ).fetchall()
    extra_rows = con.execute(
        f"SELECT __ade_rn, {shared_cols_quoted} FROM extra_in_actual"
    ).fetchall()

    # Score each pair
    scores = []
    for mi, m_row in enumerate(missing_rows):
        for ei, e_row in enumerate(extra_rows):
            matching_cols = 0
            for ci, col in enumerate(shared_cols):
                if _values_match(
                    m_row[ci + 1],
                    e_row[ci + 1],
                    col_types.get(col.lower(), "VARCHAR"),
                    tol_pct,
                    tol_abs,
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
                if col_type in (
                    "FLOAT",
                    "DOUBLE",
                    "DECIMAL",
                    "NUMERIC",
                    "REAL",
                ) or col_type.startswith("DECIMAL"):
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


def _detect_systematic_columns(
    con, shared_cols: list[str], total_rows: int, threshold: float = 0.5
) -> dict:
    """Pre-scan: try excluding each column from EXCEPT ALL to find systematic diffs.

    If excluding a single column recovers >threshold of rows as exact matches,
    that column is flagged as systematic. Collects sample value mappings by
    joining expected and actual on the remaining columns.

    Returns dict of column_name -> {diff_count, total_paired, sample_values}.
    """
    systematic = {}
    for col in shared_cols:
        remaining = [c for c in shared_cols if c != col]
        remaining_quoted = ", ".join(f'"{c}"' for c in remaining)
        # Count mismatches when this column is excluded
        miss = con.execute(f"""
            SELECT count(*) FROM (
                SELECT {remaining_quoted} FROM expected
                EXCEPT ALL
                SELECT {remaining_quoted} FROM actual
            )
        """).fetchone()[0]
        recovered = total_rows - miss
        if recovered / total_rows >= threshold:
            # This column is a systematic diff — collect distinct values from each side
            expected_vals = [
                str(r[0]) if r[0] is not None else "NULL"
                for r in con.execute(
                    f'SELECT DISTINCT "{col}" FROM expected ORDER BY 1 LIMIT 5'
                ).fetchall()
            ]
            actual_vals = [
                str(r[0]) if r[0] is not None else "NULL"
                for r in con.execute(
                    f'SELECT DISTINCT "{col}" FROM actual ORDER BY 1 LIMIT 5'
                ).fetchall()
            ]
            # Pair them up positionally for display (best-effort mapping)
            sample_values = [
                {"expected": e, "actual": a} for e, a in zip(expected_vals, actual_vals) if e != a
            ]
            systematic[col] = {
                "diff_count": total_rows - miss,
                "total_paired": total_rows,
                "sample_values": sample_values,
            }
    return systematic


def _detect_systematic_diffs(row_diffs: list[dict], threshold: float = 0.9) -> dict:
    """Detect columns that differ in >= threshold fraction of paired rows.

    Returns a dict of column_name -> {diff_count, total_paired, sample_values}.
    sample_values is a list of up to 5 distinct (expected, actual) pairs.
    """
    total = len(row_diffs)
    if total == 0:
        return {}

    # Count how often each column appears in diffs
    col_counts: dict[str, int] = {}
    col_samples: dict[str, set] = {}
    for diff in row_diffs:
        for col, vals in diff["diffs"].items():
            col_counts[col] = col_counts.get(col, 0) + 1
            if col not in col_samples:
                col_samples[col] = set()
            if len(col_samples[col]) < 5:
                col_samples[col].add((vals["expected"], vals["actual"]))

    systematic = {}
    for col, count in col_counts.items():
        if count / total >= threshold:
            systematic[col] = {
                "diff_count": count,
                "total_paired": total,
                "sample_values": [
                    {"expected": e, "actual": a} for e, a in sorted(col_samples[col])
                ],
            }
    return systematic


def _fetch_rows(con, table: str, columns: list[str], limit: int = 100) -> list[dict]:
    """Fetch rows from a table as a list of dicts."""
    cols = ", ".join(f'"{c}"' for c in columns)
    rows = con.execute(f"SELECT {cols} FROM {table} LIMIT {limit}").fetchall()
    return [
        {col: str(val) if val is not None else "NULL" for col, val in zip(columns, row)}
        for row in rows
    ]


def make_missing_relation_result(
    actual_name: str,
    expected_name: str,
    expected_path: str = None,
    actual_path: str = None,
) -> dict:
    """Create a comparison result when one relation is missing."""
    import duckdb

    found_name = None
    row_count = 0
    columns = []

    for name, path in [(expected_name, expected_path), (actual_name, actual_path)]:
        if path and Path(path).exists():
            found_name = name
            con = duckdb.connect()
            try:
                row_count = con.execute("SELECT count(*) FROM read_parquet(?)", [path]).fetchone()[
                    0
                ]
                columns = [
                    row[0]
                    for row in con.execute(
                        "SELECT column_name FROM (DESCRIBE SELECT * FROM read_parquet(?))", [path]
                    ).fetchall()
                ]
            finally:
                con.close()
            break

    missing_name = actual_name if found_name == expected_name else expected_name

    return {
        "missing_relation": missing_name,
        "found_relation": found_name,
        "found_row_count": row_count,
        "found_columns": columns,
        "expected_name": expected_name,
        "actual_name": actual_name,
        "expected_row_count": row_count if found_name == expected_name else 0,
        "actual_row_count": row_count if found_name == actual_name else 0,
        "columns": {"missing": [], "extra": [], "shared": []},
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


def render_diff_html(result: dict, model_name: str, max_rows: int = 250) -> str:
    """Render a comparison result as a self-contained HTML page."""
    import html as html_module

    def esc(s):
        return html_module.escape(str(s))

    # Handle missing relation case
    if "missing_relation" in result:
        cols_info = ""
        if result["found_columns"]:
            cols_list = ", ".join(esc(c) for c in result["found_columns"])
            cols_info = f"""
            <div class="section">
                <h3>Available columns in {esc(result['found_relation'])}</h3>
                <p class="col-list">{cols_list}</p>
                <p>{result['found_row_count']} rows</p>
            </div>"""
        return _wrap_html(
            model_name,
            f"""
        <div class="header error">
            <h2>Table Comparison: {esc(model_name)}</h2>
            <p class="error-msg">Relation <code>{esc(result['missing_relation'])}</code> not found &mdash; could not compare</p>
        </div>
        {cols_info}
        """,
        )

    cols = result["columns"]
    summary = result["summary"]

    # Column diff section
    col_html = '<div class="section"><h3>Column Diff</h3>'
    if cols["missing"]:
        col_html += '<div class="missing"><strong>Missing columns</strong> (in expected, not in actual):<ul>'
        for c in cols["missing"]:
            col_html += f"<li>{esc(c)}</li>"
        col_html += "</ul></div>"
    if cols["extra"]:
        col_html += (
            '<div class="extra"><strong>Extra columns</strong> (in actual, not in expected):<ul>'
        )
        for c in cols["extra"]:
            col_html += f"<li>{esc(c)}</li>"
        col_html += "</ul></div>"
    if cols["shared"]:
        shared_str = ", ".join(esc(c) for c in cols["shared"])
        col_html += f'<p><strong>Shared columns ({len(cols["shared"])}):</strong> {shared_str}</p>'
    col_html += "</div>"

    # Summary section
    total_expected = result["expected_row_count"]
    total_actual = result["actual_row_count"]
    summary_html = f"""
    <div class="section">
        <h3>Row Summary</h3>
        <p>Expected: {esc(result['expected_name'])} ({total_expected} rows, {len(cols['shared']) + len(cols['missing'])} columns)</p>
        <p>Actual: {esc(result['actual_name'])} ({total_actual} rows, {len(cols['shared']) + len(cols['extra'])} columns)</p>
        <table class="summary-table">
            <tr><td>Matched exactly</td><td class="num">{summary['matched_exactly']}</td></tr>
            <tr><td>Matched with diffs</td><td class="num">{summary['matched_with_diffs']}</td></tr>
            <tr class="missing"><td>Missing rows (in expected, not in actual)</td><td class="num">{summary['missing_rows']}</td></tr>
            <tr class="extra"><td>Extra rows (in actual, not in expected)</td><td class="num">{summary['extra_rows']}</td></tr>
        </table>
    </div>"""

    # Systematic diffs banner
    systematic_html = ""
    systematic = result.get("systematic_diffs", {})
    if systematic:
        n_paired = next(iter(systematic.values()))["total_paired"]
        systematic_html = f'<div class="section"><h3>Systematic Diffs (across {n_paired} paired rows)</h3><table class="diff-table">'
        systematic_html += "<tr><th>Column</th><th>Rows affected</th><th>Sample values</th></tr>"
        for col, info in systematic.items():
            samples = ", ".join(
                f'{esc(s["expected"])} &rarr; {esc(s["actual"])}' for s in info["sample_values"]
            )
            systematic_html += (
                f'<tr class="diff-row">'
                f"<td>{esc(col)}</td>"
                f'<td class="num">{info["diff_count"]}/{info["total_paired"]}</td>'
                f"<td>{samples}</td>"
                f"</tr>"
            )
        systematic_html += "</table></div>"

    # Row diffs section — compact table
    diffs_html = ""
    # Filter to rows that still have non-systematic diffs
    remaining_diffs = [d for d in result["row_diffs"] if d["diffs"]]
    if remaining_diffs:
        # Collect all columns that appear in the table
        all_id_cols = []
        all_diff_cols = []
        seen_id = set()
        seen_diff = set()
        for diff in remaining_diffs:
            for c in diff["identifying"]:
                if c not in seen_id:
                    all_id_cols.append(c)
                    seen_id.add(c)
            for c in diff["diffs"]:
                if c not in seen_diff:
                    all_diff_cols.append(c)
                    seen_diff.add(c)

        total_remaining = len(remaining_diffs)
        truncated_diffs = remaining_diffs[:max_rows]
        shown_label = f" (showing first {max_rows})" if total_remaining > max_rows else ""
        diffs_html = f'<div class="section"><h3>Row Diffs ({total_remaining} paired rows with differences{shown_label})</h3>'
        diffs_html += '<table class="compact-diff-table"><tr>'
        for c in all_id_cols:
            diffs_html += f"<th>{esc(c)}</th>"
        for c in all_diff_cols:
            diffs_html += f'<th class="diff-col">{esc(c)}</th>'
        diffs_html += "</tr>"
        for diff in truncated_diffs:
            diffs_html += "<tr>"
            for c in all_id_cols:
                val = diff["identifying"].get(c, "")
                diffs_html += f"<td>{esc(val)}</td>"
            for c in all_diff_cols:
                if c in diff["diffs"]:
                    vals = diff["diffs"][c]
                    tol_class = " within-tolerance" if vals.get("within_tolerance") else ""
                    diffs_html += (
                        f'<td class="diff-cell{tol_class}">'
                        f'{esc(vals["expected"])} &rarr; {esc(vals["actual"])}'
                        f"</td>"
                    )
                else:
                    # This column matched for this row
                    val = diff["identifying"].get(c, "")
                    diffs_html += f"<td>{esc(val)}</td>"
            diffs_html += "</tr>"
        diffs_html += "</table>"
        if total_remaining > max_rows:
            diffs_html += f'<p style="color: #808080;">... and {total_remaining - max_rows} more rows not shown</p>'
        diffs_html += "</div>"

    # Missing rows section
    missing_html = ""
    if result["missing_rows"]:
        total_missing = summary["missing_rows"]
        shown_missing = result["missing_rows"][:max_rows]
        shown_label = f" (showing first {max_rows})" if total_missing > max_rows else ""
        missing_html = f'<div class="section"><h3>Missing Rows ({total_missing} in expected, not found in actual{shown_label})</h3>'
        missing_html += _render_row_table(shown_missing, "missing")
        if total_missing > max_rows:
            missing_html += f'<p style="color: #808080;">... and {total_missing - max_rows} more rows not shown</p>'
        missing_html += "</div>"

    # Extra rows section
    extra_html = ""
    if result["extra_rows"]:
        total_extra = summary["extra_rows"]
        shown_extra = result["extra_rows"][:max_rows]
        shown_label = f" (showing first {max_rows})" if total_extra > max_rows else ""
        extra_html = f'<div class="section"><h3>Extra Rows ({total_extra} in actual, not found in expected{shown_label})</h3>'
        extra_html += _render_row_table(shown_extra, "extra")
        if total_extra > max_rows:
            extra_html += f'<p style="color: #808080;">... and {total_extra - max_rows} more rows not shown</p>'
        extra_html += "</div>"

    header_html = f"""
    <div class="header">
        <h2>Table Comparison: {esc(model_name)}</h2>
    </div>"""

    return _wrap_html(
        model_name,
        header_html
        + col_html
        + summary_html
        + systematic_html
        + diffs_html
        + missing_html
        + extra_html,
    )


def _render_row_table(rows: list[dict], css_class: str) -> str:
    """Render a list of row dicts as an HTML table."""
    import html as html_module

    if not rows:
        return ""
    cols = list(rows[0].keys())
    html = f'<table class="data-table {css_class}"><tr>'
    for c in cols:
        html += f"<th>{html_module.escape(str(c))}</th>"
    html += "</tr>"
    for row in rows:
        html += "<tr>"
        for c in cols:
            html += f"<td>{html_module.escape(str(row.get(c, '')))}</td>"
        html += "</tr>"
    html += "</table>"
    return html


def _wrap_html(model_name: str, body: str) -> str:
    """Wrap content in a full HTML page with VS Code dark theme styling."""
    import html as html_module

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Comparison: {html_module.escape(model_name)}</title>
    <style>
        body {{
            background: #1e1e1e;
            color: #d4d4d4;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 13px;
            padding: 20px;
            margin: 0;
        }}
        .header {{ margin-bottom: 20px; }}
        .header h2 {{ color: #569cd6; margin: 0 0 5px 0; }}
        .header.error .error-msg {{ color: #f44747; font-size: 14px; }}
        .section {{ margin-bottom: 24px; }}
        .section h3 {{ color: #dcdcaa; border-bottom: 1px solid #3c3c3c; padding-bottom: 4px; }}
        .col-list {{ color: #9cdcfe; }}
        .missing {{ color: #f44747; }}
        .extra {{ color: #6a9955; }}
        .within-tolerance {{ color: #dcdcaa; }}
        table {{ border-collapse: collapse; width: 100%; margin: 8px 0; }}
        th, td {{ text-align: left; padding: 4px 12px; border: 1px solid #3c3c3c; }}
        th {{ background: #2d2d2d; color: #569cd6; }}
        .summary-table {{ width: auto; }}
        .summary-table td.num {{ text-align: right; padding-left: 24px; color: #b5cea8; }}
        .summary-table tr.missing td {{ color: #f44747; }}
        .summary-table tr.extra td {{ color: #6a9955; }}
        .diff-table td.expected {{ color: #f44747; }}
        .diff-table td.actual {{ color: #6a9955; }}
        .diff-table td.num {{ text-align: right; color: #b5cea8; }}
        .diff-row.within-tolerance td {{ color: #dcdcaa; }}
        .compact-diff-table th.diff-col {{ color: #f44747; }}
        .compact-diff-table .diff-cell {{ color: #ce9178; }}
        .compact-diff-table .diff-cell.within-tolerance {{ color: #dcdcaa; }}
        .data-table.missing td {{ color: #f44747; }}
        .data-table.extra td {{ color: #6a9955; }}
        details {{ margin: 8px 0; }}
        summary {{ cursor: pointer; color: #9cdcfe; padding: 4px 0; }}
        code {{ background: #2d2d2d; padding: 2px 6px; border-radius: 3px; }}
        ul {{ margin: 4px 0; padding-left: 24px; }}
    </style>
</head>
<body>
{body}
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="Compare two parquet tables")
    parser.add_argument("--expected", required=True, help="Path to expected parquet file")
    parser.add_argument("--actual", required=True, help="Path to actual parquet file")
    parser.add_argument("--expected-name", default="expected")
    parser.add_argument("--actual-name", default="actual")
    parser.add_argument("--model-name", required=True, help="Model name for report title")
    parser.add_argument("--output", required=True, help="Output path for diff.html")
    args = parser.parse_args()

    expected_path = Path(args.expected)
    actual_path = Path(args.actual)

    if not expected_path.exists() and not actual_path.exists():
        print("[ade-bench] Both files missing, cannot compare", flush=True)
        sys.exit(1)

    if not expected_path.exists() or not actual_path.exists():
        result = make_missing_relation_result(
            args.actual_name,
            args.expected_name,
            expected_path=str(expected_path) if expected_path.exists() else None,
            actual_path=str(actual_path) if actual_path.exists() else None,
        )
    else:
        result = compare_tables(
            str(expected_path),
            str(actual_path),
            expected_name=args.expected_name,
            actual_name=args.actual_name,
        )

    html = render_diff_html(result, args.model_name)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(html)
    print(f"[ade-bench] Diff report written to {args.output}", flush=True)


if __name__ == "__main__":
    main()
