#!/usr/bin/env python3
"""Detect failing equality tests from dbt run_results.json and resolve relation pairs."""

import json
from pathlib import Path


def find_failing_equality_tests(run_results: dict) -> list[str]:
    """Find failing equality tests from run_results.json."""
    failing = []
    for result in run_results.get("results", []):
        uid = result.get("unique_id", "")
        status = result.get("status", "")
        if not uid.startswith("test."):
            continue
        if status not in ("fail", "error"):
            continue
        parts = uid.split(".")
        test_name = ".".join(parts[2:-1]) if len(parts) >= 4 else parts[-1]
        if "equality" in test_name.lower():
            failing.append(test_name)
    return failing


def resolve_relations(failing_test_names: list[str], manifest: dict) -> list[dict]:
    """Resolve failing test names to (actual, expected) relation pairs."""
    test_nodes = {}
    for node_id, node in manifest.get("nodes", {}).items():
        if node_id.startswith("test."):
            test_nodes[node.get("name", "")] = node

    results = []
    for test_name in failing_test_names:
        node = test_nodes.get(test_name)
        if not node:
            print(f"[ade-bench] Warning: test '{test_name}' not found in manifest", flush=True)
            continue

        depends_on = node.get("depends_on", {}).get("nodes", [])
        actual = None
        expected = None
        for dep in depends_on:
            dep_name = dep.split(".")[-1]
            if "solution__" in dep_name:
                expected = dep_name
            else:
                actual = dep_name

        if actual and expected:
            model_name = expected.replace("solution__", "")
            results.append({"model_name": model_name, "actual": actual, "expected": expected})
        else:
            print(f"[ade-bench] Warning: could not resolve relations for '{test_name}'", flush=True)

    return results


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Detect failing equality tests")
    parser.add_argument("--run-results", default="target/run_results.json")
    parser.add_argument("--manifest", default="target/manifest.json")
    parser.add_argument("--output", required=True, help="Path to write JSON output")
    args = parser.parse_args()

    run_results_path = Path(args.run_results)
    if not run_results_path.exists():
        print(f"[ade-bench] run_results.json not found at {run_results_path}", flush=True)
        Path(args.output).write_text("[]")
        return

    run_results = json.loads(run_results_path.read_text())
    failing = find_failing_equality_tests(run_results)

    if not failing:
        print("[ade-bench] No failing equality tests found", flush=True)
        Path(args.output).write_text("[]")
        return

    print(f"[ade-bench] Found {len(failing)} failing equality test(s): {failing}", flush=True)

    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"[ade-bench] manifest.json not found at {manifest_path}", flush=True)
        Path(args.output).write_text("[]")
        return

    manifest = json.loads(manifest_path.read_text())
    pairs = resolve_relations(failing, manifest)

    print(f"[ade-bench] Resolved {len(pairs)} relation pair(s)", flush=True)
    Path(args.output).write_text(json.dumps(pairs, indent=2))


if __name__ == "__main__":
    main()
