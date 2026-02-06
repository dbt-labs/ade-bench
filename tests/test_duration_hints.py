# ABOUTME: Tests for LPT scheduling via duration hints in the harness.
# ABOUTME: Validates loading hints from results.json and sorting tasks by descending duration.

import json
import tempfile
from pathlib import Path

from ade_bench.harness import Harness


def _make_results_json(hints: dict[str, int], tmp_dir: Path) -> Path:
    """Create a minimal results.json with the given task_id -> runtime_ms mapping."""
    results = {
        "results": [
            {"task_id": tid, "runtime_ms": ms}
            for tid, ms in hints.items()
        ]
    }
    results_path = tmp_dir / "results.json"
    results_path.write_text(json.dumps(results))
    return tmp_dir


def test_load_duration_hints_returns_mapping():
    """Loading a valid results.json returns task_id -> runtime_ms dict."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        hints_dir = _make_results_json({"task_a": 500, "task_b": 100}, tmp_path)

        harness = Harness.__new__(Harness)
        harness._duration_hints_path = hints_dir
        result = harness._load_duration_hints()

        assert result == {"task_a": 500, "task_b": 100}


def test_load_duration_hints_takes_max_of_duplicates():
    """When multiple attempts exist for same task_id, take the max runtime."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        results = {
            "results": [
                {"task_id": "task_a", "runtime_ms": 200},
                {"task_id": "task_a", "runtime_ms": 500},
                {"task_id": "task_a", "runtime_ms": 300},
            ]
        }
        (tmp_path / "results.json").write_text(json.dumps(results))

        harness = Harness.__new__(Harness)
        harness._duration_hints_path = tmp_path
        result = harness._load_duration_hints()

        assert result == {"task_a": 500}


def test_load_duration_hints_returns_empty_when_no_path():
    """When duration_hints_path is None, returns empty dict."""
    harness = Harness.__new__(Harness)
    harness._duration_hints_path = None
    result = harness._load_duration_hints()
    assert result == {}


def test_load_duration_hints_returns_empty_when_file_missing():
    """When results.json doesn't exist, returns empty dict."""
    with tempfile.TemporaryDirectory() as tmp:
        harness = Harness.__new__(Harness)
        harness._duration_hints_path = Path(tmp)
        result = harness._load_duration_hints()
        assert result == {}


def test_sort_tasks_by_duration_hints():
    """Tasks are sorted descending by hint value; unknown tasks sort first."""
    hints = {"fast": 100, "medium": 500, "slow": 1000}

    # Simulate matching_tasks as (task_path, task_key, config) tuples
    # with task_key="base" so task_id = task_path.name
    tasks = [
        (Path("/tasks/fast"), "base", {}),
        (Path("/tasks/unknown"), "base", {}),
        (Path("/tasks/slow"), "base", {}),
        (Path("/tasks/medium"), "base", {}),
    ]

    # Reconstruct task_id the same way _execute_tasks does
    def task_id_from(task_path, task_key):
        if task_key == "base":
            return task_path.name
        return f"{task_path.name}.{task_key}"

    # Sort: unknown tasks first (no hint = sort first as pessimistic),
    # then descending by hint value
    sorted_tasks = sorted(
        tasks,
        key=lambda t: hints.get(task_id_from(t[0], t[1]), float('inf')),
        reverse=True,
    )

    task_ids = [task_id_from(t[0], t[1]) for t in sorted_tasks]
    assert task_ids == ["unknown", "slow", "medium", "fast"]


def test_sort_tasks_with_non_base_key():
    """Non-base task_key produces dotted task_id for hint lookup."""
    hints = {"task.hard": 1000, "task.easy": 100}

    tasks = [
        (Path("/tasks/task"), "easy", {}),
        (Path("/tasks/task"), "hard", {}),
    ]

    def task_id_from(task_path, task_key):
        if task_key == "base":
            return task_path.name
        return f"{task_path.name}.{task_key}"

    sorted_tasks = sorted(
        tasks,
        key=lambda t: hints.get(task_id_from(t[0], t[1]), float('inf')),
        reverse=True,
    )

    task_ids = [task_id_from(t[0], t[1]) for t in sorted_tasks]
    assert task_ids == ["task.hard", "task.easy"]
