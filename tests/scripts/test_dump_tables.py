import importlib.util
import tempfile
from pathlib import Path

import duckdb


def load_module():
    spec = importlib.util.spec_from_file_location(
        "dump_tables",
        Path(__file__).parent.parent.parent / "shared" / "scripts" / "dump_tables.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestDumpTablesDuckDB:
    """Test dumping tables from DuckDB."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "test.duckdb"
        con = duckdb.connect(str(self.db_path))
        con.execute("CREATE TABLE hosts (id INT, name VARCHAR, score DOUBLE)")
        con.execute("INSERT INTO hosts VALUES (1, 'Alice', 4.5), (2, 'Bob', 3.2)")
        con.execute("CREATE TABLE reviews (id INT, host_id INT, rating INT)")
        con.execute("INSERT INTO reviews VALUES (1, 1, 5), (2, 2, 3)")
        con.close()

    def test_dump_single_table(self):
        mod = load_module()
        output_dir = Path(self.tmpdir) / "output"
        output_dir.mkdir()
        results = mod.dump_tables_duckdb(
            db_path=str(self.db_path),
            relations=["hosts"],
            output_dir=str(output_dir),
        )
        assert (output_dir / "hosts.parquet").exists()
        assert (output_dir / "hosts.csv").exists()
        assert results["hosts"]["status"] == "ok"
        assert results["hosts"]["row_count"] == 2

    def test_dump_multiple_tables(self):
        mod = load_module()
        output_dir = Path(self.tmpdir) / "output"
        output_dir.mkdir()
        results = mod.dump_tables_duckdb(
            db_path=str(self.db_path),
            relations=["hosts", "reviews"],
            output_dir=str(output_dir),
        )
        assert (output_dir / "hosts.parquet").exists()
        assert (output_dir / "reviews.parquet").exists()
        assert len(results) == 2

    def test_dump_nonexistent_table(self):
        mod = load_module()
        output_dir = Path(self.tmpdir) / "output"
        output_dir.mkdir()
        results = mod.dump_tables_duckdb(
            db_path=str(self.db_path),
            relations=["nonexistent"],
            output_dir=str(output_dir),
        )
        assert results["nonexistent"]["status"] == "not_found"

    def test_dump_with_row_limit(self):
        mod = load_module()
        output_dir = Path(self.tmpdir) / "output"
        output_dir.mkdir()
        mod.dump_tables_duckdb(
            db_path=str(self.db_path),
            relations=["hosts"],
            output_dir=str(output_dir),
            limit=1,
        )
        # Verify only 1 row exported
        con = duckdb.connect()
        row_count = con.execute(
            f"SELECT count(*) FROM read_parquet('{output_dir}/hosts.parquet')"
        ).fetchone()[0]
        assert row_count == 1

    def test_dump_empty_table(self):
        mod = load_module()
        con = duckdb.connect(str(self.db_path))
        con.execute("CREATE TABLE empty_table (id INT, name VARCHAR)")
        con.close()
        output_dir = Path(self.tmpdir) / "output"
        output_dir.mkdir()
        results = mod.dump_tables_duckdb(
            db_path=str(self.db_path),
            relations=["empty_table"],
            output_dir=str(output_dir),
        )
        assert results["empty_table"]["status"] == "ok"
        assert results["empty_table"]["row_count"] == 0
