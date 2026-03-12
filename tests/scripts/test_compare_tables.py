import importlib.util
import tempfile
from pathlib import Path

import duckdb
import pytest


def load_module():
    spec = importlib.util.spec_from_file_location(
        "compare_tables",
        Path(__file__).parent.parent.parent / "shared" / "scripts" / "compare_tables.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write_parquet(tmpdir: str, name: str, sql: str) -> Path:
    """Helper: create a parquet file from a SQL query."""
    path = Path(tmpdir) / f"{name}.parquet"
    con = duckdb.connect()
    con.execute(f"COPY ({sql}) TO '{path}' (FORMAT PARQUET)")
    con.close()
    return path


class TestColumnComparison:
    def test_identical_columns(self):
        mod = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            expected = write_parquet(tmpdir, "expected",
                "SELECT 1 as id, 'Alice' as name, 4.5 as score")
            actual = write_parquet(tmpdir, "actual",
                "SELECT 1 as id, 'Alice' as name, 4.5 as score")
            result = mod.compare_tables(str(expected), str(actual))
            assert result["columns"]["missing"] == []
            assert result["columns"]["extra"] == []
            assert len(result["columns"]["shared"]) == 3

    def test_missing_column(self):
        mod = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            expected = write_parquet(tmpdir, "expected",
                "SELECT 1 as id, 'Alice' as name, 4.5 as score")
            actual = write_parquet(tmpdir, "actual",
                "SELECT 1 as id, 'Alice' as name")
            result = mod.compare_tables(str(expected), str(actual))
            assert "score" in [c.lower() for c in result["columns"]["missing"]]

    def test_extra_column(self):
        mod = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            expected = write_parquet(tmpdir, "expected",
                "SELECT 1 as id, 'Alice' as name")
            actual = write_parquet(tmpdir, "actual",
                "SELECT 1 as id, 'Alice' as name, 4.5 as score")
            result = mod.compare_tables(str(expected), str(actual))
            assert "score" in [c.lower() for c in result["columns"]["extra"]]

    def test_column_comparison_case_insensitive(self):
        mod = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            expected = write_parquet(tmpdir, "expected",
                "SELECT 1 as ID, 'Alice' as Name")
            actual = write_parquet(tmpdir, "actual",
                "SELECT 1 as id, 'Alice' as name")
            result = mod.compare_tables(str(expected), str(actual))
            assert result["columns"]["missing"] == []
            assert result["columns"]["extra"] == []


class TestExactRowMatching:
    def test_all_rows_match(self):
        mod = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            expected = write_parquet(tmpdir, "expected",
                "SELECT * FROM (VALUES (1, 'Alice'), (2, 'Bob')) AS t(id, name)")
            actual = write_parquet(tmpdir, "actual",
                "SELECT * FROM (VALUES (2, 'Bob'), (1, 'Alice')) AS t(id, name)")
            result = mod.compare_tables(str(expected), str(actual))
            assert result["summary"]["matched_exactly"] == 2
            assert result["summary"]["missing_rows"] == 0
            assert result["summary"]["extra_rows"] == 0

    def test_missing_rows(self):
        mod = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            expected = write_parquet(tmpdir, "expected",
                "SELECT * FROM (VALUES (1, 'Alice'), (2, 'Bob')) AS t(id, name)")
            actual = write_parquet(tmpdir, "actual",
                "SELECT * FROM (VALUES (1, 'Alice')) AS t(id, name)")
            result = mod.compare_tables(str(expected), str(actual))
            assert result["summary"]["matched_exactly"] == 1
            assert result["summary"]["missing_rows"] == 1

    def test_extra_rows(self):
        mod = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            expected = write_parquet(tmpdir, "expected",
                "SELECT * FROM (VALUES (1, 'Alice')) AS t(id, name)")
            actual = write_parquet(tmpdir, "actual",
                "SELECT * FROM (VALUES (1, 'Alice'), (2, 'Bob')) AS t(id, name)")
            result = mod.compare_tables(str(expected), str(actual))
            assert result["summary"]["extra_rows"] == 1


class TestFuzzyRowMatching:
    def test_numeric_tolerance(self):
        mod = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            expected = write_parquet(tmpdir, "expected",
                "SELECT 1 as id, 4.82 as score")
            actual = write_parquet(tmpdir, "actual",
                "SELECT 1 as id, 4.80 as score")
            result = mod.compare_tables(str(expected), str(actual))
            # Should fuzzy-pair the rows (score is within 1% tolerance for pairing)
            # With 1 row, score is a systematic diff (1/1 = 100%)
            assert result["summary"]["matched_with_diffs"] == 1
            assert result["summary"]["missing_rows"] == 0
            assert "score" in result["systematic_diffs"]
            # within_tolerance is captured in sample_values context
            assert result["row_diffs"][0]["diffs"] == {}  # stripped from per-row

    def test_no_match_beyond_tolerance(self):
        mod = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            expected = write_parquet(tmpdir, "expected",
                "SELECT 1 as id, 100.0 as score")
            actual = write_parquet(tmpdir, "actual",
                "SELECT 1 as id, 50.0 as score")
            result = mod.compare_tables(str(expected), str(actual))
            # id matches so they still pair, but score is a diff
            # With 1 row, score becomes systematic (1/1 = 100%)
            assert result["summary"]["matched_with_diffs"] == 1
            assert "score" in result["systematic_diffs"]
            assert result["row_diffs"][0]["diffs"] == {}  # stripped

    def test_fuzzy_cap_exceeded(self):
        """When unmatched rows > fuzzy_row_limit, skip fuzzy matching."""
        mod = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create tables with all different rows
            expected = write_parquet(tmpdir, "expected",
                "SELECT unnest(range(600)) as id, 'a' as name")
            actual = write_parquet(tmpdir, "actual",
                "SELECT unnest(range(600, 1200)) as id, 'b' as name")
            result = mod.compare_tables(str(expected), str(actual), fuzzy_row_limit=500)
            assert result["summary"]["matched_with_diffs"] == 0
            assert result["summary"]["missing_rows"] == 600


class TestSystematicDiffs:
    def test_all_rows_differ_in_one_column(self):
        """When every paired row differs in the same column, it's systematic."""
        mod = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            expected = write_parquet(tmpdir, "expected",
                "SELECT * FROM (VALUES (1, 'true', 10), (2, 'false', 20), (3, 'true', 30)) AS t(id, flag, val)")
            actual = write_parquet(tmpdir, "actual",
                "SELECT * FROM (VALUES (1, 't', 10), (2, 'f', 20), (3, 't', 30)) AS t(id, flag, val)")
            result = mod.compare_tables(str(expected), str(actual))
            assert result["summary"]["matched_with_diffs"] == 3
            # flag should be systematic (3/3 = 100%)
            assert "flag" in result["systematic_diffs"]
            sys = result["systematic_diffs"]["flag"]
            assert sys["diff_count"] == 3
            assert sys["total_paired"] == 3
            # Sample values should contain the distinct mappings
            samples = {(s["expected"], s["actual"]) for s in sys["sample_values"]}
            assert ("true", "t") in samples
            assert ("false", "f") in samples
            # Per-row diffs should have flag stripped
            for diff in result["row_diffs"]:
                assert "flag" not in diff["diffs"]

    def test_mixed_columns_only_systematic_detected(self):
        """Only columns above threshold are systematic; sporadic ones stay per-row."""
        mod = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            # 3 rows: flag differs in all 3, val differs in only 1
            expected = write_parquet(tmpdir, "expected",
                "SELECT * FROM (VALUES (1, 'true', 10), (2, 'false', 20), (3, 'true', 30)) AS t(id, flag, val)")
            actual = write_parquet(tmpdir, "actual",
                "SELECT * FROM (VALUES (1, 't', 10), (2, 'f', 20), (3, 't', 99)) AS t(id, flag, val)")
            result = mod.compare_tables(str(expected), str(actual))
            # flag is systematic, val is not (1/3 = 33%)
            assert "flag" in result["systematic_diffs"]
            assert "val" not in result["systematic_diffs"]
            # The row with val diff should still show val in per-row diffs
            rows_with_val = [d for d in result["row_diffs"] if "val" in d["diffs"]]
            assert len(rows_with_val) == 1

    def test_no_systematic_when_below_threshold(self):
        """Columns differing in <90% of rows are not systematic."""
        mod = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            # 10 rows, flag differs in 8 (80% < 90% threshold)
            rows_expected = ", ".join(
                f"({i}, '{'true' if i < 8 else 'same'}', {i * 10})" for i in range(10))
            rows_actual = ", ".join(
                f"({i}, '{'t' if i < 8 else 'same'}', {i * 10})" for i in range(10))
            expected = write_parquet(tmpdir, "expected",
                f"SELECT * FROM (VALUES {rows_expected}) AS t(id, flag, val)")
            actual = write_parquet(tmpdir, "actual",
                f"SELECT * FROM (VALUES {rows_actual}) AS t(id, flag, val)")
            result = mod.compare_tables(str(expected), str(actual))
            # 8/10 rows differ => 2 match exactly, 8 matched with diffs
            # flag appears in 8/8 paired rows = 100% => IS systematic
            # (because the 2 matching rows are exact matches, not paired)
            assert "flag" in result["systematic_diffs"]


class TestNullHandling:
    def test_nulls_match(self):
        mod = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            expected = write_parquet(tmpdir, "expected",
                "SELECT 1 as id, NULL::VARCHAR as name")
            actual = write_parquet(tmpdir, "actual",
                "SELECT 1 as id, NULL::VARCHAR as name")
            result = mod.compare_tables(str(expected), str(actual))
            assert result["summary"]["matched_exactly"] == 1

    def test_null_vs_value(self):
        mod = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            expected = write_parquet(tmpdir, "expected",
                "SELECT 1 as id, NULL::VARCHAR as name")
            actual = write_parquet(tmpdir, "actual",
                "SELECT 1 as id, 'Alice' as name")
            result = mod.compare_tables(str(expected), str(actual))
            assert result["summary"]["matched_exactly"] == 0


class TestEmptyTables:
    def test_both_empty(self):
        mod = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            expected = write_parquet(tmpdir, "expected",
                "SELECT id, name FROM (VALUES (1, 'x')) AS t(id, name) WHERE false")
            actual = write_parquet(tmpdir, "actual",
                "SELECT id, name FROM (VALUES (1, 'x')) AS t(id, name) WHERE false")
            result = mod.compare_tables(str(expected), str(actual))
            assert result["summary"]["matched_exactly"] == 0
            assert result["summary"]["missing_rows"] == 0
            assert result["summary"]["extra_rows"] == 0

    def test_expected_empty_actual_has_rows(self):
        mod = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            expected = write_parquet(tmpdir, "expected",
                "SELECT id, name FROM (VALUES (1, 'x')) AS t(id, name) WHERE false")
            actual = write_parquet(tmpdir, "actual",
                "SELECT 1 as id, 'Alice' as name")
            result = mod.compare_tables(str(expected), str(actual))
            assert result["summary"]["extra_rows"] == 1
