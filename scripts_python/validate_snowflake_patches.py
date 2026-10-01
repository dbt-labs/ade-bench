#!/usr/bin/env python3
"""
Validate that all Snowflake-path patches apply cleanly by simulating the
container lifecycle for each task that has a Snowflake variant:

  migration → setup/changes.patch → setup/changes.snowflake.patch
           → solutions/changes.patch → solutions/changes.snowflake.patch

Each task is tested once per migration (e.g. once for dbt, once for dbt-fusion).

A coverage check at the end confirms every .patch file in the repo was exercised.
Patches belonging to tasks with no Snowflake variant are excluded — they are only
applied on DuckDB and are covered by the existing DuckDB CI.
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


def files_created_by_patch(patch_file: Path) -> list[str]:
    """Return relative paths of files that this patch creates (source is /dev/null).

    Used to pre-delete files from the project before applying solution patches —
    setup.sh may remove these files via shell commands (not patches) to create the
    puzzle state, but our simulation only applies patches.
    """
    created = []
    lines = patch_file.read_text().splitlines()
    for i, line in enumerate(lines):
        if line.startswith("--- /dev/null") and i + 1 < len(lines):
            next_line = lines[i + 1]
            if next_line.startswith("+++ b/"):
                created.append(next_line[6:])  # strip "+++ b/"
    return created


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


def validate_migration_patches(
    snowflake_tasks: dict[str, list[str]],
) -> tuple[list[dict], set[Path]]:
    """Validate each migration patch against a fresh copy of the shared project."""
    results: list[dict] = []
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
            results.append(
                {
                    "name": f"migration/{migration_dir_name}",
                    "status": "ERROR",
                    "detail": f"Project directory not found: {project_dir.relative_to(REPO_ROOT)}",
                }
            )
            continue

        with tempfile.TemporaryDirectory() as tmp:
            tmp_project = Path(tmp) / project_name
            shutil.copytree(project_dir, tmp_project, symlinks=True)
            success, output = apply_patch(tmp_project, patch_file)

        results.append(
            {
                "name": f"migration/{migration_dir_name}",
                "status": "PASS" if success else "FAIL",
                "detail": output,
            }
        )

    return results, validated


def _validate_patch_sequence(
    tmp_project: Path,
    base_patch: Path | None,
    snowflake_patch: Path | None,
    script_path: Path,
    label_prefix: str,
    pre_delete_created_files: bool = False,
) -> tuple[list[dict], set[Path]]:
    """Apply base patch then snowflake delta. Returns (results, validated_paths).

    Base patch failure is OK if the script applies it with '|| true'.
    Snowflake patch uses --forward to skip already-applied hunks (mirrors setup.sh behavior).

    pre_delete_created_files: if True, delete any files the patches would CREATE before
    applying them. Set this for solution patches — setup.sh may remove these files via
    shell commands (not patches) to create the puzzle, so our patch-only simulation needs
    to do the same.
    """
    results: list[dict] = []
    validated: set[Path] = set()

    if base_patch and base_patch.exists():
        validated.add(base_patch.resolve())
        if pre_delete_created_files:
            for rel_path in files_created_by_patch(base_patch):
                target = tmp_project / rel_path
                if target.exists():
                    target.unlink()
        success, output = apply_patch(tmp_project, base_patch)
        optional = patch_is_optional(script_path, base_patch.name)
        if not success and not optional:
            results.append(
                {
                    "name": f"{label_prefix}/{base_patch.name}",
                    "status": "FAIL",
                    "detail": output,
                }
            )
        else:
            results.append(
                {
                    "name": f"{label_prefix}/{base_patch.name}",
                    "status": "PASS",
                    "detail": output,
                }
            )

    if snowflake_patch and snowflake_patch.exists():
        validated.add(snowflake_patch.resolve())
        if pre_delete_created_files:
            for rel_path in files_created_by_patch(snowflake_patch):
                target = tmp_project / rel_path
                if target.exists():
                    target.unlink()
        success, output = apply_patch(tmp_project, snowflake_patch, extra_flags=["--forward"])
        results.append(
            {
                "name": f"{label_prefix}/{snowflake_patch.name}",
                "status": "PASS" if success else "FAIL",
                "detail": output,
            }
        )

    return results, validated


def validate_task_patches(
    snowflake_tasks: dict[str, list[str]],
) -> tuple[list[dict], set[Path]]:
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

            # Include migration name in label when task has >1 migration
            label = f"{task_id}[{migration_dir}]" if len(migration_dirs) > 1 else task_id

            with tempfile.TemporaryDirectory() as tmp:
                tmp_project = Path(tmp) / project_name
                shutil.copytree(project_dir, tmp_project, symlinks=True)

                # Stage 1: migration
                if migration_patch.exists():
                    success, _ = apply_patch(tmp_project, migration_patch)
                    if not success:
                        # Migration failure reported by validate_migration_patches()
                        continue

                # Stage 2: setup patches
                setup_results, setup_validated = _validate_patch_sequence(
                    tmp_project,
                    setup_base,
                    setup_snow,
                    task_dir / "setup.sh",
                    f"{label}/setup",
                )
                all_results.extend(setup_results)
                all_validated.update(setup_validated)

                # Stage 3: solution patches (applied on top of setup state).
                # Pre-delete files the patches will create: setup.sh may remove them
                # via shell commands (not patches) to produce the puzzle state.
                sol_results, sol_validated = _validate_patch_sequence(
                    tmp_project,
                    sol_base,
                    sol_snow,
                    task_dir / "solution.sh",
                    f"{label}/solutions",
                    pre_delete_created_files=True,
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
    results: list[dict] = []

    for patch_file in sorted(REPO_ROOT.glob("**/*.patch")):
        # Skip worktrees — they are copies of the repo, not the canonical source
        if ".worktrees" in patch_file.parts:
            continue

        # Migration patches are covered by validate_migration_patches()
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
            results.append(
                {
                    "name": f"coverage/{patch_file.relative_to(REPO_ROOT)}",
                    "status": "FAIL",
                    "detail": "Patch file exists but was not exercised by this script",
                }
            )

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
