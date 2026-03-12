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
            # but score shows as a diff annotated with within_tolerance=True
            assert result["summary"]["matched_with_diffs"] == 1
            assert result["summary"]["missing_rows"] == 0
            assert result["row_diffs"][0]["diffs"]["score"]["within_tolerance"] is True

    def test_no_match_beyond_tolerance(self):
        mod = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            expected = write_parquet(tmpdir, "expected",
                "SELECT 1 as id, 100.0 as score")
            actual = write_parquet(tmpdir, "actual",
                "SELECT 1 as id, 50.0 as score")
            result = mod.compare_tables(str(expected), str(actual))
            # id matches so they still pair, but score is a diff
            assert result["summary"]["matched_with_diffs"] == 1
            assert len(result["row_diffs"][0]["diffs"]) == 1

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
