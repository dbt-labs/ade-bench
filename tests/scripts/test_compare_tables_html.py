# tests/scripts/test_compare_tables_html.py
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
    path = Path(tmpdir) / f"{name}.parquet"
    con = duckdb.connect()
    con.execute(f"COPY ({sql}) TO '{path}' (FORMAT PARQUET)")
    con.close()
    return path


class TestHTMLGeneration:
    def test_generates_valid_html(self):
        mod = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            expected = write_parquet(tmpdir, "expected",
                "SELECT 1 as id, 'Alice' as name, 4.5 as score")
            actual = write_parquet(tmpdir, "actual",
                "SELECT 1 as id, 'Alice' as name, 3.0 as score")
            result = mod.compare_tables(str(expected), str(actual))
            html = mod.render_diff_html(result, "snap__hosts")
            assert "<html" in html or "<div" in html
            assert "snap__hosts" in html
            assert "score" in html

    def test_missing_relation_html(self):
        mod = load_module()
        result = mod.make_missing_relation_result(
            "snap__hosts", "solution__snap__hosts",
            expected_path="/app/comparisons/solution__snap__hosts.parquet"
        )
        html = mod.render_diff_html(result, "snap__hosts")
        assert "not found" in html.lower()

    def test_systematic_diffs_banner(self):
        """Systematic diffs render as a banner, not per-row."""
        mod = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            expected = write_parquet(tmpdir, "expected",
                "SELECT * FROM (VALUES (1, 'true', 10), (2, 'false', 20), (3, 'true', 30)) AS t(id, flag, val)")
            actual = write_parquet(tmpdir, "actual",
                "SELECT * FROM (VALUES (1, 't', 10), (2, 'f', 20), (3, 't', 30)) AS t(id, flag, val)")
            result = mod.compare_tables(str(expected), str(actual))
            html = mod.render_diff_html(result, "test_model")
            assert "Systematic Diffs" in html
            assert "flag" in html
            # Should show the arrow mapping
            assert "&rarr;" in html
            # Should NOT have a per-row diffs section (all diffs were systematic)
            assert "Row Diffs" not in html

    def test_compact_table_with_mixed_diffs(self):
        """Rows with non-systematic diffs show in a compact table."""
        mod = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            expected = write_parquet(tmpdir, "expected",
                "SELECT * FROM (VALUES (1, 'true', 10), (2, 'false', 20), (3, 'true', 30)) AS t(id, flag, val)")
            actual = write_parquet(tmpdir, "actual",
                "SELECT * FROM (VALUES (1, 't', 10), (2, 'f', 20), (3, 't', 99)) AS t(id, flag, val)")
            result = mod.compare_tables(str(expected), str(actual))
            html = mod.render_diff_html(result, "test_model")
            # Should have both systematic banner and compact table
            assert "Systematic Diffs" in html
            assert "Row Diffs" in html
            # Compact table should show val diff with arrow
            assert "99" in html

    def test_column_diff_section(self):
        mod = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            expected = write_parquet(tmpdir, "expected",
                "SELECT 1 as id, 'Alice' as name, 4.5 as score")
            actual = write_parquet(tmpdir, "actual",
                "SELECT 1 as id, 'Alice' as name")
            result = mod.compare_tables(str(expected), str(actual))
            html = mod.render_diff_html(result, "snap__hosts")
            assert "Missing" in html or "missing" in html
            assert "score" in html
