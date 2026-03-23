import importlib.util
from pathlib import Path


def load_module():
    spec = importlib.util.spec_from_file_location(
        "detect_failing",
        Path(__file__).parent.parent.parent
        / "shared"
        / "scripts"
        / "detect_failing_equality_tests.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestFindFailingEqualityTests:
    def test_one_failing_equality(self):
        mod = load_module()
        run_results = {
            "results": [
                {"unique_id": "test.proj.AUTO_snap__hosts_existence.abc", "status": "pass"},
                {"unique_id": "test.proj.AUTO_snap__hosts_equality.def", "status": "fail"},
                {"unique_id": "test.proj.AUTO_dim_evolution_equality.ghi", "status": "pass"},
            ]
        }
        result = mod.find_failing_equality_tests(run_results)
        assert result == ["AUTO_snap__hosts_equality"]

    def test_no_failures(self):
        mod = load_module()
        run_results = {
            "results": [
                {"unique_id": "test.proj.AUTO_snap__hosts_equality.abc", "status": "pass"},
            ]
        }
        assert mod.find_failing_equality_tests(run_results) == []

    def test_ignores_non_equality_failures(self):
        mod = load_module()
        run_results = {
            "results": [
                {"unique_id": "test.proj.AUTO_snap__hosts_existence.abc", "status": "fail"},
            ]
        }
        assert mod.find_failing_equality_tests(run_results) == []

    def test_ignores_model_nodes(self):
        mod = load_module()
        run_results = {
            "results": [
                {"unique_id": "model.proj.some_model", "status": "error"},
            ]
        }
        assert mod.find_failing_equality_tests(run_results) == []

    def test_handles_error_status(self):
        """Tests with status 'error' should also be detected."""
        mod = load_module()
        run_results = {
            "results": [
                {"unique_id": "test.proj.AUTO_snap__hosts_equality.abc", "status": "error"},
            ]
        }
        assert mod.find_failing_equality_tests(run_results) == ["AUTO_snap__hosts_equality"]


class TestResolveRelations:
    def test_resolve_from_manifest(self):
        mod = load_module()
        manifest = {
            "nodes": {
                "test.proj.AUTO_snap__hosts_equality.abc": {
                    "name": "AUTO_snap__hosts_equality",
                    "depends_on": {
                        "nodes": [
                            "model.proj.snap__hosts",
                            "seed.proj.solution__snap__hosts",
                        ]
                    },
                }
            }
        }
        result = mod.resolve_relations(["AUTO_snap__hosts_equality"], manifest)
        assert len(result) == 1
        assert result[0]["model_name"] == "snap__hosts"
        assert result[0]["actual"] == "snap__hosts"
        assert result[0]["expected"] == "solution__snap__hosts"

    def test_not_in_manifest(self):
        mod = load_module()
        result = mod.resolve_relations(["AUTO_missing_equality"], {"nodes": {}})
        assert result == []
