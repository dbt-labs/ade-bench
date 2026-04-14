# Patch Failure Detection Design

**Date:** 2026-04-15  
**Status:** Approved

## Problem

When a `patch` command fails inside a shell script (setup.sh, migration.sh, solution.sh), the failure is currently invisible to the harness. Two independent gaps cause this:

1. **Shell gap**: Scripts have no `set -e`, so a failing `patch` exits non-zero but the script continues running subsequent commands as if nothing happened.
2. **Harness gap**: `session.send_keys([command, "Enter"], block=True)` waits for `tmux wait -S done` to fire, but never inspects the exit code of the command that ran before it.

Real example: `airbnb001` on the Snowflake/dbt-fusion variant — the migration patch fails on `models/dim/dim_dates.sql` with "Hunk #1 FAILED", writes a `.rej` file, and the trial continues into the agent phase with a corrupted project state.

## Scope

Shell scripts that apply patches and must succeed to establish a valid trial environment:
- `tasks/*/setup.sh`
- `shared/migrations/*/migration.sh`
- `tasks/*/solution.sh` (reference agent — if its patch fails, expected outputs are wrong)

Out of scope:
- `test_setup` in task.yaml (currently only `dbt run` commands, no patches)
- `run-tests.sh` (test failures are expected and handled separately)

## Design

### 1. Harness exit-code capture

A new helper `run_script_checked` in `ade_bench/setup/utils.py` wraps any shell script invocation to capture its exit code via a file written inside the container:

```python
def run_script_checked(
    session: TmuxSession,
    container,
    command: str,
    max_timeout_sec: float = 180.0,
) -> int:
    """Run a shell command via tmux and return its exit code."""
    checked = f"{command}; echo $? > /tmp/.ade_exit_code"
    session.send_keys([checked, "Enter"], block=True, max_timeout_sec=max_timeout_sec)
    result = container.exec_run(["cat", "/tmp/.ade_exit_code"])
    return int(result.output.decode().strip())
```

Three call sites are updated to use this helper:

| File | Script | On failure |
|------|--------|------------|
| `ade_bench/setup/base_setup.py` | `setup.sh` | raise `RuntimeError` → harness catches → `FailureMode.SETUP_FAILED` |
| `ade_bench/setup/migration_setup.py` | `migration.sh` | raise `RuntimeError` → harness catches → `FailureMode.SETUP_FAILED` |
| `ade_bench/agents/sage_agent.py` | `solution.sh` | return `AgentResult(failure_mode=FailureMode.UNKNOWN_AGENT_ERROR)` |

The harness's `_run_setup` already catches all exceptions and maps them to `FailureMode.SETUP_FAILED` (harness.py:687). No new exception class is needed.

### 2. Shell script hardening

All `setup.sh`, `migration.sh`, and `solution.sh` files get `set -euo pipefail` added as the first line after the shebang. This propagates any inner `patch` failure to the script's exit code, which the harness then catches via the mechanism above.

`|| true` is the explicit opt-out for steps that are expected or allowed to fail. Two legitimate uses:

**Optional patches** — airbnb003's first patch is intentionally applied with `|| true` because the migration script changes the same files afterward. This stays as-is.

**Intentional dbt build failures** — some tasks set up a broken state that the agent must fix. These `dbt run` calls need `|| true` so the setup succeeds even though the build fails. Only scripts where the patch actually causes a downstream compile error qualify.

### 3. Per-task `dbt run` audit

All setup.sh scripts with a bare `dbt run` are audited. The outcome:

**Remove `|| true`** (was overly defensive — patch only changes data, build succeeds):
- `helixops_saas001` — removes a column from a SELECT, valid SQL
- `helixops_saas002` — removes a column from two SELECTs, valid SQL
- `helixops_saas003` — replaces tier logic with raw value, valid SQL
- `helixops_saas004` — removes a column from a SELECT, valid SQL
- `helixops_saas011` — same tier logic change as saas003, valid SQL

**Add `|| true`** (bare `dbt run` with a patch that breaks compilation):
- `airbnb001` — patch introduces `surrogate_key` deprecation warning-as-error; `dbt run` fails and that failure IS the task prompt

**Already correct — keep as-is:**
- `helixops_saas005` — patch removes `email` and adds `email_address` reference that doesn't exist; compile error is intentional, `|| true` is correct

### 4. analytics_engineering005 patch consolidation

`setup/changes.duckdb.patch` and `setup/changes.snowflake.patch` are identical. Consolidate into a single `setup/changes.patch` and remove the db_type conditional from `setup.sh`:

```bash
# Before
if [[ "$*" == *"--db-type=snowflake"* ]]; then
    patch -p1 < /app/setup/changes.snowflake.patch
else
    patch -p1 < /app/setup/changes.duckdb.patch
fi

# After
patch -p1 < /app/setup/changes.patch
```

The redundant `.duckdb.patch` and `.snowflake.patch` files are deleted.

## File change summary

**New file:**
- `ade_bench/setup/utils.py` — `run_script_checked` helper

**Modified Python:**
- `ade_bench/setup/base_setup.py` — use `run_script_checked`, raise on failure
- `ade_bench/setup/migration_setup.py` — use `run_script_checked`, raise on failure
- `ade_bench/agents/sage_agent.py` — use `run_script_checked`, return INFRA_FAILURE

**Modified shell scripts:**
- All `tasks/*/setup.sh` — add `set -euo pipefail`
- All `shared/migrations/*/migration.sh` — add `set -euo pipefail`
- All `tasks/*/solution.sh` — add `set -euo pipefail`
- `tasks/airbnb001/setup.sh` — add `dbt run || true`
- `tasks/helixops_saas001–004,011/setup.sh` — remove `|| true` from `dbt run`

**Modified task files (analytics_engineering005):**
- `tasks/analytics_engineering005/setup.sh` — remove db_type conditional
- `tasks/analytics_engineering005/setup/changes.patch` — new consolidated file
- `tasks/analytics_engineering005/setup/changes.duckdb.patch` — deleted
- `tasks/analytics_engineering005/setup/changes.snowflake.patch` — deleted

## Conventions going forward

- All `setup.sh`, `migration.sh`, and `solution.sh` files start with `set -euo pipefail`
- `dbt run || true` is used only when the task's broken initial state causes a compile/runtime error
- `patch ... || true` is used only for patches that are genuinely optional (e.g. conditionally skipped by a later migration step)
- Any bare `patch` without `|| true` must succeed or the trial is marked INFRA_FAILURE
