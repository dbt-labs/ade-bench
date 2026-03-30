# helixops_saas Benchmark Tasks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create 25 ADE-bench benchmark tasks that test an AI agent's ability to make targeted dbt model changes against the helixops_saas shared project.

**Architecture:** Each task lives in `tasks/helixops_saas0NN/`, contains a `task.yaml`, `setup.sh`, `solution.sh`, a `solutions/` directory with correct SQL, and a `tests/` directory with SQL validation queries. The shared project (`shared/projects/dbt/helixops_saas`) and database (`shared/databases/duckdb/helixops_saas.duckdb`) are referenced but not modified by individual tasks. setup.sh puts the project into a broken/incomplete state; the agent's job is to fix it; solution.sh is the answer key.

**Tech Stack:** bash, dbt-core 1.10.11, dbt-duckdb 1.9.3, DuckDB 1.3.0. DuckDB-only for now (Snowflake deferred). No external dbt packages.

---

## Task Classification

Tasks fall into three categories based on the model changes required:

**Type A — Remove-and-restore:** The field already exists in the correct model. `setup.sh` removes it with `sed`. The agent must identify what is missing and restore it. `solution.sh` copies back the full correct SQL.

**Type B — Genuine addition:** The field does not currently exist. `setup.sh` runs a baseline dbt build. The agent must implement a new column from scratch. `solution.sh` applies the correct implementation.

**Type C — Logic change:** The field exists but with wrong logic. `setup.sh` applies the broken logic. The agent must fix it. `solution.sh` restores correct logic.

---

## Common Patterns

### task.yaml template

```yaml
task_id: helixops_saasNNN
status: ready
description: One-line description
prompts:
  - key: base
    prompt: |-
      <task description — goal-oriented, no project context, no command hints>
author_name: joel
difficulty: easy
tags:
  - dbt
  - helixops_saas
variants:
- db_type: duckdb
  db_name: helixops_saas
  project_type: dbt
  project_name: helixops_saas
- db_type: duckdb
  db_name: helixops_saas
  project_type: dbt-fusion
  project_name: helixops_saas
solution_seeds:
  - table_name: <affected_mart_or_fact_table>
```

### setup.sh template (Type A — remove a column)

```bash
#!/bin/bash
# Remove target column from model, then build baseline
sed -i '/    column_expression_to_remove,/d' models/path/to/model.sql
dbt run --select model_name
```

> Note: `sed -i` works on Linux (inside Docker). No need for macOS fallback since tasks run in containers.

### solution.sh template

```bash
#!/bin/bash
# Restore correct model SQL from solutions/ and rebuild
SOLUTIONS_DIR="$(dirname "$(readlink -f "${BASH_SOURCE}")")/solutions"
cp "$SOLUTIONS_DIR/model_name.sql" models/path/to/model_name.sql
dbt run --select model_name
```

### SQL test template

Tests return **0 rows** to pass, **≥1 row** to fail.

```sql
-- tests/column_name_exists.sql
-- Fails if the column is missing or null for every row
select 1
from {{ ref('target_model') }}
where column_name is null
having count(*) = count(1)
limit 1
```

Or for simple presence test (fails if query errors because column doesn't exist):

```sql
-- tests/column_name_not_null.sql
select 1
from {{ ref('target_model') }}
where column_name is not null
limit 0
```

For data-correctness tests using solution seeds, see `CONTRIBUTING.md` — run `ade run helixops_saasNNN --agent sage --db duckdb --seed` to auto-generate.

---


## Tasks

| # | Task ID | Source model(s) | Target model | Type | Prompt | setup.sh sed pattern | solution notes |
|---|---------|----------------|--------------|------|--------|---------------------|----------------|
| 1 | helixops_saas001 | stg_accounts | dim_accounts | A | "Add billing_country to dim_accounts." | `/    a.billing_country,/d` | add missing column from parent model |
| 2 | helixops_saas002 | stg_accounts | dim_accounts + mart_account_360 | A | "Add the owning team to the account 360." | remove `a.owner_team` from dim_accounts and `a.owner_team` from mart_account_360 | multi-layer propagation — must add to dim_accounts first, then mart_account_360 |
| 3 | helixops_saas003 | stg_workspaces | int_workspace_daily_metrics + int_account_daily_usage | C+A | "Please filter sandbox usage out of daily usage reporting." | (1) strip CASE from stg_workspaces — replace with `trim(env_tier) as environment_tier` (raw values exposed); (2) remove `w.environment_tier` from int_workspace_daily_metrics | agent must propagate environment_tier through metrics and filter, handling raw values 'sandbox'/'sbx' |
| 4 | helixops_saas004 | stg_users | int_workspace_roster | C | "I need to be able to work out what departments users belong to across their workspace memberships. Please add a department column — you can infer it from job title if needed." | remove `u.department` from int_workspace_roster | agent must recognize department already exists in stg_users and add it directly rather than inferring from title |
| 5 | helixops_saas005 | stg_users | int_account_users | C | "Can you fix the failing model." | (1) remove `lower(trim(email_addr)) as email` from stg_users; (2) rename `u.email` → `u.email_address` in int_account_users; (3) remove `u.email` from int_workspace_roster (no hints) | solution adds `email_address` to stg_users; agent must not just rename column in intermediate |
| 6 | helixops_saas006 | int_subscription_history + int_account_billing_snapshot | mart_account_360 | B | "Please add net_mrr to the account 360, based on contracted price less discount, divided by 12 if billed annually." | add `ls.list_price_usd` to int_account_billing_snapshot (so b.list_price_usd, b.discount_pct, b.billing_cycle are all available in mart_account_360); run baseline dbt build | correct solution is `b.effective_monthly_value_usd as net_mrr` — not recalculating from inputs; tests validate column exists with correct values |
| 7 | helixops_saas007 | int_subscription_history | int_account_billing_snapshot + mart_account_360 + mart_account_health | B | "Add region and segment to int_account_billing_snapshot as a single geo_segment column, and carry it through to the account 360 and account health marts." | none (run baseline build) | add `ls.region || ' / ' || ls.segment as geo_segment` to int_account_billing_snapshot; add `b.geo_segment` to mart_account_360 and mart_account_health; tests confirm geo_segment is present in those three models and absent from fct_support_tickets and fct_monthly_revenue |
| 8 | helixops_saas008 | stg_accounts | dim_accounts + mart_account_360 + mart_account_health + fct_support_tickets | C | "stg_accounts has account_status instead of customer_status, please rename and propagate." | none (run baseline build) | rename in stg_accounts; update all downstream references through full DAG |
| 9 | helixops_saas009 | stg_accounts | dim_accounts | B | "Please create a v2 of dim_accounts with account_status renamed to customer_status — this will become the primary version in 6 months." | none (run baseline build) | create dim_accounts_v2.sql as a new model with customer_status; old dim_accounts remains unchanged; tests verify dim_accounts_v2 exists with customer_status column and dim_accounts still has account_status |
| 10 | helixops_saas010 | stg_workspaces | int_account_workspaces | B | "Please filter out archived workspaces after the staging layer." | none (run baseline build) | add WHERE workspace_status != 'archived' to int_account_workspaces |
| 11 | helixops_saas011 | stg_workspaces | int_account_workspaces + dim_accounts | C | "The Falcon Works sandbox isn't showing up in dim_accounts." | strip CASE from stg_workspaces environment_tier — replace with `lower(trim(env_tier)) as environment_tier` (exposes raw 'sbx' value); run baseline build | agent must trace 'sbx' back to staging normalization and fix the CASE to include 'sbx' → 'sandbox' |
| 12 | helixops_saas012 | int_monthly_revenue_prep | fct_monthly_revenue | refactor | "Please move the monthly revenue prep model into being a CTE for the main revenue model." | none (run baseline build) | inline int_monthly_revenue_prep SQL as a CTE in fct_monthly_revenue; delete int_monthly_revenue_prep.sql; SQL tests verify fct_monthly_revenue still has all expected columns; structural verification (model file deleted) requires a non-SQL test |
| 13 | helixops_saas013 | stg_invoice_line_items | int_invoice_finance + fct_monthly_revenue | C | "Helio Systems' onboarding fees are being treated as recurring revenue, please fix it." | run DuckDB UPDATE: `UPDATE raw_invoice_line_items SET recurring_hint = 'Y' WHERE line_id IN ('L7102', 'L7220', 'L7342')`; run dbt build | fix is_recurring_line CASE in stg_invoice_line_items to explicitly exclude line_type='onboarding_addon' regardless of recurring_hint |
| 14 | helixops_saas014 | stg_workspace_usage_daily | mart_account_360 | A | "Please add total API calls to the account 360." | remove api_calls from all 7 models: stg_workspace_usage_daily, int_workspace_daily_metrics, int_account_daily_usage, int_account_engagement, fct_daily_account_usage, mart_account_360, mart_account_health; run baseline build | agent must propagate through full DAG (stg → metrics → daily_usage → engagement → 360); must not jump directly from staging to mart |
| 15 | helixops_saas015 | int_support_sla | fct_support_tickets | B | two variants: (base) "We updated our support SLAs effective 2025-06-16 at 08:00 UTC. Please move priority and response_sla_minutes into a new seed with valid_from and valid_to timestamps, and update the models accordingly. New SLAs: urgent=20min, high=90min, medium=300min, standard=1500min." (low) same but says low=1500min instead of standard. | none (run baseline build) | create seed with priority/response_sla_minutes/valid_from/valid_to; join in int_support_sla on priority + opened_at between valid_from and valid_to; 'standard' variant is a trap — actual priority value in data is 'low' (staging normalizes to low); valid_from must be timestamp '2025-06-16 08:00:00' not just date |
| 16 | helixops_saas016 | int_support_sla | fct_support_tickets | B | "We have new SLA targets for enterprise accounts only, effective 2025-06-16 at 08:00 UTC. Please update the SLA model so enterprise accounts get: urgent=20min, high=45min, medium=120min, standard=900min. Other segments keep existing SLAs." | none (run baseline build) | seed must include segment column; join on priority + segment + opened_at between valid_from and valid_to; 'standard' is the trap again — enterprise segment value in data is 'enterprise' (lowercase); non-enterprise rows keep old CASE logic or fallback rows in seed |
| 17 | helixops_saas017 | stg_users | int_workspace_roster | already-done | "Add department to the workspace roster." | none (no setup changes — department is already in the model) | correct behavior is no changes; marked expected-pass for the none agent |
