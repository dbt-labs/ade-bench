---
name: ade-bench-cross-db-tasks
description: Use when authoring or debugging ade-bench tasks that must run on both DuckDB and Snowflake, including shared project migrations, setup patches, and solution patches
---

# ADE-Bench Cross-DB Task Authoring

## Overview

Tasks in ade-bench can target DuckDB (default) or Snowflake. A task's files go through a deterministic **four-stage lifecycle**. Patches that ignore this order produce context mismatches or "reversed patch" prompts that block execution.

## Container Lifecycle (in order)

```
1. MIGRATION   shared/migrations/<name>/migration.sh + migration.patch
               — Converts shared project files from DuckDB to Snowflake syntax
2. SETUP       tasks/<id>/setup.sh  +  tasks/<id>/setup/changes.patch
                                       tasks/<id>/setup/changes.snowflake.patch (optional)
               — Creates the puzzle state the agent must solve
3. AGENT       (agent works here)
4. SOLUTION    tasks/<id>/solution.sh  +  tasks/<id>/solutions/changes.patch
                                          tasks/<id>/solutions/changes.snowflake.patch (optional)
```

**Critical:** Migration runs before setup and solution. Any line migration touches is in its post-migration state when patches run.

## Patch File Pattern

Always apply the base patch, then conditionally apply the snowflake delta. This applies to both `setup.sh` and `solution.sh`:

```bash
patch -p1 < /app/setup/changes.patch           # always (use /sage/solutions/ for solution.sh)

if [[ "$*" == *"--db-type=snowflake"* ]]; then
    patch -p1 < /app/setup/changes.snowflake.patch  # additive delta only
fi
```

**Never** use if/else to choose between two alternative patches. The base patch handles DuckDB; the snowflake patch stacks on top for Snowflake.

`changes.snowflake.patch` is a **delta** — it only contains changes that differ from the DuckDB result. It never replicates what migration already did.

## Migration Guidelines

**Migration's job:** Convert DuckDB-specific syntax to Snowflake equivalents across all tasks sharing a project.

- Schema names: `schema: main` → `schema: public`
- Date functions: `STRPTIME(...)` → `TO_DATE(TO_TIMESTAMP(...))`
- Generator functions, STRFTIME, etc.

**Don't add migration hunks for files that setup removes.** If setup strips a config block entirely, migration touching a field inside that block is wasted work that breaks setup's patch. Example: if `setup/changes.patch` deletes an entire `{{ config(...) }}` block from `src_hosts.sql`, migration should not change `schema=` inside that same block.

## Modifying dbt_project.yml: use yq, not patch

The migration process calls `yaml.safe_load` / `yaml.safe_dump` on `dbt_project.yml` to update the profile name. This completely reformats the file — sorted keys, no comments, different whitespace. Any patch against the original layout will fail.

**Use `yq` for all `dbt_project.yml` changes** in setup.sh and solution.sh:

```bash
# Add a variable
yq -i '.vars.surrogate_key_treat_nulls_as_empty_strings = true' dbt_project.yml

# Delete a variable
yq -i 'del(.vars.quickbooks.using_department)' dbt_project.yml

# Disable a package model
yq -i '.models.quickbooks_source["stg_quickbooks__refund_receipt"]["+enabled"] = false' dbt_project.yml
```

`yq` performs semantic YAML operations so key order and formatting don't matter.

## Setup Patch Guidelines

Setup creates the puzzle. `setup/changes.patch` runs after migration.

**When setup's base patch can't match post-migration content** (e.g. migration changed `schema="main"` to `schema="public"` in a line the setup patch must remove):

```bash
# setup.sh
patch -p1 --batch < /app/setup/changes.patch || true   # graceful fail on Snowflake

if [[ "$*" == *"--db-type=snowflake"* ]]; then
    patch -p1 --batch --forward < /app/setup/changes.snowflake.patch
fi
```

- `--batch`: prevents interactive "Apply anyway?" prompt (avoids blocking)
- `--forward`: skips reversed/already-applied hunks without prompting
- `|| true`: base patch may partially fail on Snowflake; that's expected

`setup/changes.snowflake.patch` is the DuckDB base patch with post-migration values substituted (e.g. `schema="public"` instead of `schema="main"` in the removed lines).

## Solution Patch Guidelines

### Context line mismatch (migration changed a context line)

If migration rewrites a line that appears as a **context line** (` `) in `changes.patch`, drop it from context:

```diff
# Before — STRPTIME is a context line; migration changes it to TO_DATE(...)
 @@ -11,7 +11,7 @@
          transaction_type,
          CAST(STRPTIME(transaction_created_date, '%m/%d/%Y %H:%M:%S') AS DATE) AS transaction_created_date,
          transaction_modified_date,
 -        product_id,
 +        product_id::varchar AS product_id,

# After — start hunk after the changed line, no STRPTIME context
 @@ -14,4 +14,4 @@
 -        product_id,
 +        product_id::varchar AS product_id,
          quantity,
          purchase_order_id,
          customer_order_id,
```

### `-` line mismatch (migration changed a line being removed)

If migration rewrites a line that is a **`-` line** (a line being deleted), 0-context doesn't help — the removed line must match exactly. Use `changes.snowflake.patch` with the post-migration value:

```patch
# changes.snowflake.patch — removes config block after migration changed schema
@@ -1,9 +1,0 @@
-{{
-    config(materialized="table", schema="public", ...)
-}}
-
```

### Never duplicate migration in the snowflake patch

Before adding anything to `changes.snowflake.patch`, check whether migration already makes that change. If migration already converts STRPTIME or changes schema, the solution patch must not repeat it — patch will detect it as reversed and block.

## Quick Diagnosis

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Hunk #N FAILED` in solution | Migration changed a context line | Drop that context line from the hunk |
| `Reversed patch detected! Assume -R?` | Snowflake patch duplicates migration | Delete or update the snowflake patch |
| Setup `Hunk #1 FAILED` then solution fails | Migration changed a `-` line in setup patch | Add `setup/changes.snowflake.patch` + `--batch \|\| true` |
| `dbt_project.yml` patch fails on Snowflake | Migration reformatted the file via yaml.safe_dump | Switch to `yq` for all dbt_project.yml edits |
| Silent wrong output | Base patch failed, no error shown | Add `set -e` or check with `--dry-run` |

## Real Examples

**analytics_engineering007** (`tasks/analytics_engineering007/solutions/changes.patch`): Migration converts `CAST(STRPTIME(...))` → `TO_DATE(...)` in `fact_inventory.sql`. The solution's `changes.patch` had STRPTIME as a context line — fragile fuzz match. Fixed by starting the hunk at line 14 (`@@ -14,4`) instead of line 11 (`@@ -11,7`), skipping the migrated line entirely. The solution's snowflake patch (which also tried to convert STRPTIME) was deleted since migration already did it.

**airbnb003** (`tasks/airbnb003/setup/`): Migration changes `schema="main"` → `schema="public"` inside the config block of `src_hosts.sql`. The setup's `changes.patch` removes that entire config block but has `schema="main"` in the `-` lines — fails after migration. Fixed by adding `setup/changes.snowflake.patch` (same removal with `schema="public"`) and using `--batch || true` on the base patch so it fails gracefully, then the snowflake patch completes the removal.

**airbnb002** (`tasks/airbnb002/solution.sh`): Solution needs to add `surrogate_key_treat_nulls_as_empty_strings: true` to `dbt_project.yml`. Using patch fails because migration's yaml.safe_dump reformatted the file. Fixed with:
```bash
yq -i '.vars.surrogate_key_treat_nulls_as_empty_strings = true' dbt_project.yml
```

**quickbooks003** (`tasks/quickbooks003/solution.sh`): Solution needs to disable three package models and delete a variable from `dbt_project.yml`. Patch was unreliable after migration reformatting. Fixed with yq:
```bash
yq -i '.models.quickbooks_source["stg_quickbooks__refund_receipt"]["+enabled"] = false' dbt_project.yml
yq -i 'del(.vars.quickbooks.using_department)' dbt_project.yml
```
