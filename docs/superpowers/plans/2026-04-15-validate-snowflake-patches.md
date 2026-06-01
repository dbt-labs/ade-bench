# Validate Snowflake Patches CI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a GitHub Actions workflow that validates all Snowflake-path patches apply cleanly — migration patches, setup patches, and solution patches — catching regressions before they reach production.

**Architecture:** A Python script (`scripts_python/validate_snowflake_patches.py`) simulates the full Snowflake container lifecycle for every task that has a Snowflake variant: (1) apply migration patch to a temp copy of the shared project, (2) apply setup patches in the correct order, (3) apply solution patches in the correct order. A coverage check at the end confirms that every `.patch` file in the repo was exercised. A GitHub Actions workflow runs this on PRs that touch relevant paths.

**Tech Stack:** Python 3.10, PyYAML (already a project dependency), `patch` (standard Unix tool, available on ubuntu-latest), GitHub Actions

---

## Background: Patch Execution Order

From `skills/ade-bench-cross-db-tasks/SKILL.md`, the container lifecycle is:

```
1. MIGRATION   shared/migrations/<name>/migration.patch
               — Converts shared project from DuckDB to Snowflake syntax

2. SETUP       tasks/<id>/setup.sh
               — applies setup/changes.patch          (all variants, || true if may fail)
               — applies setup/changes.snowflake.patch (Snowflake only, --forward)

3. AGENT       (not simulated in CI)

4. SOLUTION    tasks/<id>/solution.sh
               — applies solutions/changes.patch          (all variants, || true if may fail)
               — applies solutions/changes.snowflake.patch (Snowflake only, --forward)
```

For each task with a Snowflake variant, CI must simulate stages 1, 2, and 4 against a temp copy of the shared project. Stage 3 (agent work) is not simulated — solution patches are applied directly from the post-setup state.

Base patches (`changes.patch`) may be applied with `|| true` in setup.sh/solution.sh when migration has already changed lines the patch needs to match. In that case a hunk failure is expected and must not fail CI. Detect this by grepping the script for the pattern `changes.patch.*|| true`.

Patches that belong to tasks with **no Snowflake variant** are tested only by the DuckDB CI and are explicitly excluded from coverage.

## File Structure

- **Create:** `scripts_python/validate_snowflake_patches.py` — discovery + validation logic
- **Create:** `.github/workflows/validate-patches.yml` — PR workflow

---

### Task 1: Write the patch validation script

**Files:**
- Create: `scripts_python/validate_snowflake_patches.py`

- [ ] **Step 1: Create the script**

```python
#!/usr/bin/env python3
"""
Validate that all Snowflake-path patches apply cleanly by simulating the
container lifecycle for each task that has a Snowflake variant:

  migration → setup/changes.patch → setup/changes.snowflake.patch
           → solutions/changes.patch → solutions/changes.snowflake.patch

A coverage check at the end confirms every .patch file in the repo was exercised.
"""

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
MIGRATIONS_DIR = REPO_ROOT / "shared" / "migrations"
PROJECTS_DIR = REPO_ROOT / "shared" / "projects" / "dbt"
TASKS_DIR = REPO_ROOT / "tasks"


def project_name_from_migration(migration_dir_name: str) -> str:
    """Extract project name from migration directory name.

    e.g. 'airbnb__duckdb_to_snowflake'     → 'airbnb'
         'airbnb__duckdb_to_snowflake_dbtf' → 'airbnb'
    """
    return migration_dir_name.split("__")[0]


def patch_is_optional(script_path: Path, patch_filename: str) -> bool:
    """Return True if the script applies this patch file with '|| true'.

    Matches patterns like: patch ... changes.patch || true
    """
    if not script_path.exists():
        return False
    return bool(
        re.search(
            rf"{re.escape(patch_filename)}.*\|\|\s*true",
            script_path.read_text(),
        )
    )


def apply_patch(
    project_dir: Path,
    patch_file: Path,
    extra_flags: list[str] | None = None,
) -> tuple[bool, str]:
    """Apply a patch to a project directory. Returns (success, combined output)."""
    cmd = ["patch", "-p1", "--batch"] + (extra_flags or [])
    with open(patch_file) as patch_fh:
        result = subprocess.run(
            cmd,
            stdin=patch_fh,
            capture_output=True,
            text=True,
            cwd=project_dir,
        )
    return result.returncode == 0, (result.stdout + result.stderr).strip()


def build_snowflake_task_map() -> dict[str, list[str]]:
    """Return {task_id: [migration_dir, ...]} for tasks with Snowflake variants.

    A task may have multiple Snowflake migrations (e.g. dbt and dbt-fusion variants).
    All are returned so setup/solution patches are validated against each migration.
    """
    tasks: dict[str, list[str]] = {}
    for task_yaml in sorted(TASKS_DIR.glob("*/task.yaml")):
        task_id = task_yaml.parent.name
        with open(task_yaml) as f:
            data = yaml.safe_load(f)
        for variant in data.get("variants", []):
            if variant.get("db_type") == "snowflake" and variant.get("migration_directory"):
                migration_dir = variant["migration_directory"]
                tasks.setdefault(task_id, [])
                if migration_dir not in tasks[task_id]:
                    tasks[task_id].append(migration_dir)
    return tasks


def validate_migration_patches(snowflake_tasks: dict[str, list[str]]) -> tuple[list[dict], set[Path]]:
    """Validate each migration patch against a fresh copy of the shared project."""
    results = []
    validated: set[Path] = set()

    seen_migrations: set[str] = set()
    for migration_dirs in snowflake_tasks.values():
        seen_migrations.update(migration_dirs)

    for migration_dir_name in sorted(seen_migrations):
        migration_dir = MIGRATIONS_DIR / migration_dir_name
        patch_file = migration_dir / "migration.patch"
        if not patch_file.exists():
            continue

        validated.add(patch_file.resolve())
        project_name = project_name_from_migration(migration_dir_name)
        project_dir = PROJECTS_DIR / project_name

        if not project_dir.exists():
            results.append({
                "name": f"migration/{migration_dir_name}",
                "status": "ERROR",
                "detail": f"Project directory not found: {project_dir.relative_to(REPO_ROOT)}",
            })
            continue

        with tempfile.TemporaryDirectory() as tmp:
            tmp_project = Path(tmp) / project_name
            shutil.copytree(project_dir, tmp_project, symlinks=True)
            success, output = apply_patch(tmp_project, patch_file)

        results.append({
            "name": f"migration/{migration_dir_name}",
            "status": "PASS" if success else "FAIL",
            "detail": output,
        })

    return results, validated


def _validate_patch_sequence(
    tmp_project: Path,
    base_patch: Path | None,
    snowflake_patch: Path | None,
    script_path: Path,
    label_prefix: str,
) -> tuple[list[dict], set[Path], bool]:
    """Apply base patch then snowflake delta. Returns (results, validated_paths, ok_to_continue).

    ok_to_continue is False only if an unexpected hard failure occurs.
    """
    results: list[dict] = []
    validated: set[Path] = set()
    ok = True

    if base_patch and base_patch.exists():
        validated.add(base_patch.resolve())
        success, output = apply_patch(tmp_project, base_patch)
        optional = patch_is_optional(script_path, base_patch.name)
        if not success and not optional:
            results.append({
                "name": f"{label_prefix}/{base_patch.name}",
                "status": "FAIL",
                "detail": output,
            })
            ok = False
        else:
            results.append({
                "name": f"{label_prefix}/{base_patch.name}",
                "status": "PASS",
                "detail": output,
            })

    if snowflake_patch and snowflake_patch.exists():
        validated.add(snowflake_patch.resolve())
        success, output = apply_patch(tmp_project, snowflake_patch, extra_flags=["--forward"])
        results.append({
            "name": f"{label_prefix}/{snowflake_patch.name}",
            "status": "PASS" if success else "FAIL",
            "detail": output,
        })
        if not success:
            ok = False

    return results, validated, ok


def validate_task_patches(snowflake_tasks: dict[str, list[str]]) -> tuple[list[dict], set[Path]]:
    """For each Snowflake task, simulate the full patch lifecycle in a temp directory.

    Each task is tested once per migration (e.g. once for dbt, once for dbt-fusion).
    Order: migration → setup patches → solution patches.
    """
    all_results: list[dict] = []
    all_validated: set[Path] = set()

    for task_id, migration_dirs in sorted(snowflake_tasks.items()):
        task_dir = TASKS_DIR / task_id
        setup_base = task_dir / "setup" / "changes.patch"
        setup_snow = task_dir / "setup" / "changes.snowflake.patch"
        sol_base = task_dir / "solutions" / "changes.patch"
        sol_snow = task_dir / "solutions" / "changes.snowflake.patch"

        has_patches = any(p.exists() for p in [setup_base, setup_snow, sol_base, sol_snow])
        if not has_patches:
            continue

        for migration_dir in migration_dirs:
            project_name = project_name_from_migration(migration_dir)
            project_dir = PROJECTS_DIR / project_name
            migration_patch = MIGRATIONS_DIR / migration_dir / "migration.patch"

            # Label includes migration when task has >1 migration to distinguish results
            label = f"{task_id}[{migration_dir}]" if len(migration_dirs) > 1 else task_id

            with tempfile.TemporaryDirectory() as tmp:
                tmp_project = Path(tmp) / project_name
                shutil.copytree(project_dir, tmp_project, symlinks=True)

                # Stage 1: migration
                if migration_patch.exists():
                    success, output = apply_patch(tmp_project, migration_patch)
                    if not success:
                        # Migration failure is reported by validate_migration_patches()
                        # Skip task-level patch checks since migration is the prerequisite
                        continue

                # Stage 2: setup patches
                setup_results, setup_validated, _ = _validate_patch_sequence(
                    tmp_project,
                    setup_base,
                    setup_snow,
                    task_dir / "setup.sh",
                    f"{label}/setup",
                )
                all_results.extend(setup_results)
                all_validated.update(setup_validated)

                # Stage 3: solution patches (applied on top of setup state)
                sol_results, sol_validated, _ = _validate_patch_sequence(
                    tmp_project,
                    sol_base,
                    sol_snow,
                    task_dir / "solution.sh",
                    f"{label}/solutions",
                )
                all_results.extend(sol_results)
                all_validated.update(sol_validated)

    return all_results, all_validated


def validate_coverage(
    snowflake_task_ids: set[str],  # tasks with at least one Snowflake variant
    validated_patches: set[Path],
) -> list[dict]:
    """Check every .patch file in the repo was exercised.

    Patches in tasks with no Snowflake variant are legitimately excluded
    (they're only applied on DuckDB and are covered by the existing DuckDB CI).
    """
    results = []

    for patch_file in sorted(REPO_ROOT.glob("**/*.patch")):
        # Skip migration patches — covered by validate_migration_patches()
        if patch_file.parent.parent == MIGRATIONS_DIR:
            continue

        # Determine owning task (if any)
        try:
            rel = patch_file.relative_to(TASKS_DIR)
            task_id = rel.parts[0]
        except ValueError:
            task_id = None

        if task_id and task_id not in snowflake_task_ids:
            # Task has no Snowflake variant — covered by DuckDB CI only
            continue

        if patch_file.resolve() not in validated_patches:
            results.append({
                "name": f"coverage/{patch_file.relative_to(REPO_ROOT)}",
                "status": "FAIL",
                "detail": "Patch file exists but was not exercised by this script",
            })

    return results


def main() -> None:
    print("Validating Snowflake patches...\n")

    snowflake_tasks = build_snowflake_task_map()
    snowflake_task_ids: set[str] = set(snowflake_tasks.keys())

    migration_results, migration_validated = validate_migration_patches(snowflake_tasks)
    task_results, task_validated = validate_task_patches(snowflake_tasks)

    all_validated = migration_validated | task_validated
    coverage_results = validate_coverage(snowflake_task_ids, all_validated)

    all_results = migration_results + task_results + coverage_results

    for r in all_results:
        icon = "✅" if r["status"] == "PASS" else "❌"
        print(f"{icon} [{r['status']}] {r['name']}")
        if r["status"] != "PASS":
            print(f"       {r['detail']}")

    passed = sum(1 for r in all_results if r["status"] == "PASS")
    failed = len(all_results) - passed
    print(f"\nResults: {passed} passed, {failed} failed out of {len(all_results)} patches")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run locally and verify all current patches pass**

```bash
uv run python scripts_python/validate_snowflake_patches.py
```

Expected output: all 96 patches show `✅ [PASS]`, no coverage failures, exit code 0.

If a patch fails, the output shows which hunk failed. Check:
- Migration failures: the file referenced in the patch hunk exists in `shared/projects/dbt/{project}/`
- Setup/solution failures: the file exists and hasn't diverged from what the patch expects post-migration
- Coverage failures: a `.patch` file belongs to a Snowflake task but wasn't reached — check that `task.yaml` has `db_type: snowflake` with `migration_directory` set

Notes on exclusions in coverage check:
- `.worktrees/` paths are skipped (copies of the repo, not canonical source)

- [ ] **Step 3: Commit**

```bash
git add scripts_python/validate_snowflake_patches.py
git commit -m "feat: add script to validate all snowflake-path patches"
```

---

### Task 2: Write the GitHub Actions workflow

**Files:**
- Create: `.github/workflows/validate-patches.yml`

- [ ] **Step 1: Create the workflow file**

```yaml
name: Validate Snowflake Patches

on:
  pull_request:
    branches:
      - main
    paths:
      - "shared/migrations/**"
      - "shared/projects/dbt/**"
      - "tasks/*/setup/changes*.patch"
      - "tasks/*/solutions/changes*.patch"
      - "tasks/*/task.yaml"
      - ".github/workflows/validate-patches.yml"
      - "scripts_python/validate_snowflake_patches.py"

permissions:
  contents: read
  pull-requests: read

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  validate-patches:
    name: Validate Snowflake patches apply cleanly
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd

      - name: Set up Python
        uses: actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405
        with:
          python-version: "3.10"

      - name: Install uv
        uses: astral-sh/setup-uv@803947b9bd8e9f986429fa0c5a41c367cd732b41

      - name: Install dependencies
        run: uv sync

      - name: Validate Snowflake patches
        run: uv run python scripts_python/validate_snowflake_patches.py
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/validate-patches.yml
git commit -m "ci: add workflow to validate snowflake patches on PRs"
```
