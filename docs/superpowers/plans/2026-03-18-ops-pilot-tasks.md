# ops_pilot Benchmark Tasks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create 25 ADE-bench benchmark tasks that test an AI agent's ability to make targeted dbt model changes against the ops_pilot shared project.

**Architecture:** Each task lives in `tasks/ops_pilot0NN/`, contains a `task.yaml`, `setup.sh`, `solution.sh`, a `solutions/` directory with correct SQL, and a `tests/` directory with SQL validation queries. The shared project (`shared/projects/dbt/ops_pilot`) and database (`shared/databases/duckdb/ops_pilot.duckdb`) are referenced but not modified by individual tasks. setup.sh puts the project into a broken/incomplete state; the agent's job is to fix it; solution.sh is the answer key.

**Tech Stack:** bash, dbt-core 1.10.11, dbt-duckdb 1.9.3, DuckDB 1.3.0. DuckDB-only for now (Snowflake deferred). No external dbt packages.

---

## Task Classification

Tasks fall into three categories based on the model changes required:

**Type A — Remove-and-restore:** The field already exists in the correct model. `setup.sh` removes it with `sed`. The agent must identify what is missing and restore it. `solution.sh` copies back the full correct SQL.

**Type B — Genuine addition:** The field does not currently exist. `setup.sh` runs a baseline dbt build. The agent must implement a new column from scratch. `solution.sh` applies the correct implementation.

**Type C — Logic change:** The field exists but with wrong logic. `setup.sh` applies the broken logic. The agent must fix it. `solution.sh` restores correct logic.

---

## Common Patterns

### task.yaml template (DuckDB only)

```yaml
task_id: ops_pilotNNN
status: ready
description: One-line description
prompts:
  - key: base
    prompt: |-
      You are working in a dbt project called ops_pilot. <task description>.
      When you are done, run `dbt run --select <model>` to rebuild the affected model(s).
author_name: joel
difficulty: easy
tags:
  - dbt
  - ops_pilot
variants:
- db_type: duckdb
  db_name: ops_pilot
  project_type: dbt
  project_name: ops_pilot
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

For data-correctness tests using solution seeds, see `CONTRIBUTING.md` — run `ade run ops_pilotNNN --agent sage --db duckdb --seed` to auto-generate.

---

## Files to Create (all tasks)

```
tasks/
  ops_pilot001/  task.yaml, setup.sh, solution.sh, solutions/dim_accounts.sql, tests/billing_country_in_dim_accounts.sql
  ops_pilot002/  task.yaml, setup.sh, solution.sh, solutions/mart_account_360.sql, tests/owner_team_in_mart_account_360.sql
  ops_pilot003/  task.yaml, setup.sh, solution.sh, solutions/int_workspace_daily_metrics.sql, tests/environment_tier_in_metrics.sql
  ops_pilot004/  task.yaml, setup.sh, solution.sh, solutions/fct_daily_account_usage.sql, tests/workspace_days_reporting_exists.sql
  ops_pilot005/  task.yaml, setup.sh, solution.sh, solutions/int_workspace_roster.sql, tests/department_in_int_workspace_roster.sql
  ops_pilot006/  task.yaml, setup.sh, solution.sh, solutions/int_account_users.sql, tests/user_status_in_int_account_users.sql
  ops_pilot007/  task.yaml, setup.sh, solution.sh, solutions/int_subscription_history.sql, tests/support_tier_in_int_subscription_history.sql
  ops_pilot008/  task.yaml, setup.sh, solution.sh, solutions/int_account_billing_snapshot.sql, tests/billing_cycle_in_snapshot.sql
  ops_pilot009/  task.yaml, setup.sh, solution.sh, solutions/mart_account_360.sql, tests/discount_pct_in_mart_account_360.sql
  ops_pilot010/  task.yaml, setup.sh, solution.sh, solutions/dim_accounts.sql, tests/customer_status_in_dim_accounts.sql
  ops_pilot011/  task.yaml, setup.sh, solution.sh, solutions/int_account_workspaces.sql, tests/archived_workspaces_excluded.sql
  ops_pilot012/  task.yaml, setup.sh, solution.sh, solutions/mart_account_health.sql, tests/active_workspace_count_in_health.sql
  ops_pilot013/  task.yaml, setup.sh, solution.sh, solutions/dim_accounts.sql, tests/sandbox_workspace_count_in_dim_accounts.sql
  ops_pilot014/  task.yaml, setup.sh, solution.sh, solutions/mart_account_360.sql, tests/latest_invoice_status_in_360.sql
  ops_pilot015/  task.yaml, setup.sh, solution.sh, solutions/int_account_billing_snapshot.sql, tests/latest_payment_status_in_snapshot.sql
  ops_pilot016/  task.yaml, setup.sh, solution.sh, solutions/int_monthly_revenue_prep.sql, tests/gross_revenue_usd_in_revenue_prep.sql
  ops_pilot017/  task.yaml, setup.sh, solution.sh, solutions/int_invoice_finance.sql, tests/onboarding_excluded_from_recurring.sql
  ops_pilot018/  task.yaml, setup.sh, solution.sh, solutions/fct_monthly_revenue.sql, tests/one_time_revenue_in_fct_monthly_revenue.sql
  ops_pilot019/  task.yaml, setup.sh, solution.sh, solutions/mart_account_health.sql, tests/has_past_due_invoice_in_health.sql
  ops_pilot020/  task.yaml, setup.sh, solution.sh, solutions/mart_account_360.sql, tests/avg_active_users_7d_in_360.sql
  ops_pilot021/  task.yaml, setup.sh, solution.sh, solutions/mart_account_360.sql, tests/total_api_calls_30d_in_360.sql
  ops_pilot022/  task.yaml, setup.sh, solution.sh, solutions/mart_account_360.sql, tests/open_ticket_count_in_360.sql
  ops_pilot023/  task.yaml, setup.sh, solution.sh, solutions/fct_support_tickets.sql, tests/first_response_minutes_in_fct_support_tickets.sql
  ops_pilot024/  task.yaml, setup.sh, solution.sh, solutions/fct_support_tickets.sql, tests/plan_name_in_fct_support_tickets.sql
  ops_pilot025/  task.yaml, setup.sh, solution.sh, solutions/int_workspace_roster.sql, tests/is_primary_in_int_workspace_roster.sql
```

---

## Task 1: ops_pilot001 — billing_country in dim_accounts (Type A)

**Files:**
- Create: `tasks/ops_pilot001/task.yaml`
- Create: `tasks/ops_pilot001/setup.sh`
- Create: `tasks/ops_pilot001/solution.sh`
- Create: `tasks/ops_pilot001/solutions/dim_accounts.sql` (copy of correct dim_accounts)
- Create: `tasks/ops_pilot001/tests/billing_country_in_dim_accounts.sql`

- [ ] **Step 1: Create task.yaml**

```yaml
task_id: ops_pilot001
status: ready
description: Add billing_country from stg_accounts to dim_accounts
prompts:
  - key: base
    prompt: |-
      You are working in a dbt project called ops_pilot. The `dim_accounts` model
      is missing the `billing_country` column. Add it by sourcing the value from
      the upstream staging model that contains it. When done, run
      `dbt run --select dim_accounts` to rebuild the model.
author_name: joel
difficulty: easy
tags:
  - dbt
  - ops_pilot
variants:
- db_type: duckdb
  db_name: ops_pilot
  project_type: dbt
  project_name: ops_pilot
solution_seeds:
  - table_name: dim_accounts
```

- [ ] **Step 2: Create solutions/dim_accounts.sql** (complete correct SQL — copy from `shared/projects/dbt/ops_pilot/models/marts/dim_accounts.sql`)

- [ ] **Step 3: Create setup.sh**

```bash
#!/bin/bash
sed -i '/    a.billing_country,/d' models/marts/dim_accounts.sql
dbt run --select dim_accounts
```

- [ ] **Step 4: Create solution.sh**

```bash
#!/bin/bash
SOLUTIONS_DIR="$(dirname "$(readlink -f "${BASH_SOURCE}")")/solutions"
cp "$SOLUTIONS_DIR/dim_accounts.sql" models/marts/dim_accounts.sql
dbt run --select dim_accounts
```

- [ ] **Step 5: Create tests/billing_country_in_dim_accounts.sql**

```sql
-- Fails if billing_country is not present or always null
select 1
from {{ ref('dim_accounts') }}
where billing_country is not null
limit 0
```

- [ ] **Step 6: Commit**

```bash
git add tasks/ops_pilot001/
git commit -m "feat(ops_pilot001): billing_country in dim_accounts"
```

---

## Task 2: ops_pilot002 — owner_team in mart_account_360 (Type A)

- [ ] **Create task.yaml** — prompt: `mart_account_360` is missing `owner_team`. Add it from the upstream account dimension.
- [ ] **Create solutions/mart_account_360.sql** — correct mart_account_360 with `a.owner_team`
- [ ] **Create setup.sh** — `sed -i '/    a.owner_team,/d' models/marts/mart_account_360.sql && dbt run --select mart_account_360`
- [ ] **Create solution.sh** — copy from solutions/, `dbt run --select mart_account_360`
- [ ] **Create tests/owner_team_in_mart_account_360.sql** — presence check
- [ ] **Commit**

---

## Task 3: ops_pilot003 — environment_tier in int_workspace_daily_metrics (Type A)

- [ ] **Create task.yaml** — prompt: `int_workspace_daily_metrics` is missing `environment_tier`. Add it from the workspace data joined in this model.
- [ ] **Create solutions/int_workspace_daily_metrics.sql** — correct version with `w.environment_tier`
- [ ] **Create setup.sh** — `sed -i '/    w.environment_tier,/d' models/intermediate/int_workspace_daily_metrics.sql && dbt run --select int_workspace_daily_metrics+`
- [ ] **Create solution.sh** — copy from solutions/, `dbt run --select int_workspace_daily_metrics+`
- [ ] **Create tests/environment_tier_in_metrics.sql** — presence check on `int_workspace_daily_metrics`
- [ ] **Commit**

---

## Task 4: ops_pilot004 — workspace_days_reporting in fct_daily_account_usage (Type A)

> Note: `fct_daily_account_usage` is at account-day grain. `workspace_status` from task list is ambiguous at this grain. This task instead uses `workspace_days_reporting` (workspace count per account-day), which is already in the model and is the relevant metric. The setup removes it.

- [ ] **Create task.yaml** — prompt: `fct_daily_account_usage` is missing the `workspace_days_reporting` column showing how many workspaces reported usage that day. Add it from the upstream aggregation.
- [ ] **Create solutions/fct_daily_account_usage.sql** — correct version
- [ ] **Create setup.sh** — `sed -i '/    u.workspace_days_reporting,/d' models/marts/fct_daily_account_usage.sql && dbt run --select fct_daily_account_usage`
- [ ] **Create solution.sh** — copy from solutions/, `dbt run --select fct_daily_account_usage`
- [ ] **Create tests/workspace_days_reporting_exists.sql** — presence check
- [ ] **Commit**

---

## Task 5: ops_pilot005 — department in int_workspace_roster (Type A)

- [ ] **Create task.yaml** — prompt: `int_workspace_roster` is missing the `department` column for each workspace member. Add it from the upstream user data.
- [ ] **Create solutions/int_workspace_roster.sql** — correct version with `u.department`
- [ ] **Create setup.sh** — `sed -i '/    u.department,/d' models/intermediate/int_workspace_roster.sql && dbt run --select int_workspace_roster`
- [ ] **Create solution.sh** — copy from solutions/, `dbt run --select int_workspace_roster`
- [ ] **Create tests/department_in_roster.sql** — presence check
- [ ] **Commit**

---

## Task 6: ops_pilot006 — user_status in int_account_users (Type A)

- [ ] **Create task.yaml** — prompt: `int_account_users` is missing the `user_status` column. Add it from the staged user data.
- [ ] **Create solutions/int_account_users.sql** — correct version
- [ ] **Create setup.sh** — `sed -i '/    u.user_status,/d' models/intermediate/int_account_users.sql && dbt run --select int_account_users+`
- [ ] **Create solution.sh** — copy, `dbt run --select int_account_users+`
- [ ] **Create tests/user_status_in_account_users.sql** — presence check
- [ ] **Commit**

---

## Task 7: ops_pilot007 — support_tier in int_subscription_history (Type A)

- [ ] **Create task.yaml** — prompt: `int_subscription_history` is missing `support_tier`. Add it from the plan data that is already joined in this model.
- [ ] **Create solutions/int_subscription_history.sql** — correct version with `p.support_tier`
- [ ] **Create setup.sh** — `sed -i '/    p.support_tier,/d' models/intermediate/int_subscription_history.sql && dbt run --select int_subscription_history+`
- [ ] **Create solution.sh** — copy, `dbt run --select int_subscription_history+`
- [ ] **Create tests/support_tier_in_subscription_history.sql** — presence check
- [ ] **Commit**

---

## Task 8: ops_pilot008 — billing_cycle in int_account_billing_snapshot (Type A)

- [ ] **Create task.yaml** — prompt: `int_account_billing_snapshot` is missing `billing_cycle`. It should come from the latest subscription data.
- [ ] **Create solutions/int_account_billing_snapshot.sql** — correct version with `ls.billing_cycle`
- [ ] **Create setup.sh** — `sed -i '/    ls.billing_cycle,/d' models/intermediate/int_account_billing_snapshot.sql && dbt run --select int_account_billing_snapshot+`
- [ ] **Create solution.sh** — copy, `dbt run --select int_account_billing_snapshot+`
- [ ] **Create tests/billing_cycle_in_snapshot.sql** — presence check
- [ ] **Commit**

---

## Task 9: ops_pilot009 — discount_pct in mart_account_360 (Type A)

- [ ] **Create task.yaml** — prompt: `mart_account_360` is missing `discount_pct`. Add it from the billing snapshot data already joined in this model.
- [ ] **Create solutions/mart_account_360.sql** — correct version with `b.discount_pct`
- [ ] **Create setup.sh** — `sed -i '/    b.discount_pct,/d' models/marts/mart_account_360.sql && dbt run --select mart_account_360`
- [ ] **Create solution.sh** — copy, `dbt run --select mart_account_360`
- [ ] **Create tests/discount_pct_in_360.sql** — presence check
- [ ] **Commit**

---

## Task 10: ops_pilot010 — Rename account_status to customer_status in dim_accounts (Type C)

> This is a logic/naming change. setup.sh keeps the model as-is (with `account_status`). The agent must rename it.

- [ ] **Create task.yaml** — difficulty: easy. Prompt: "In `dim_accounts`, rename the column `account_status` to `customer_status`. Rebuild `dim_accounts` and any downstream models that reference `account_status` from this table."

  > Note: This task requires checking downstream consumers. Only `dim_accounts` itself needs renaming in the SELECT; downstream models use `account_status` from dim_accounts. The solution adds `account_status as customer_status` (or renames in dim_accounts and updates downstream). The simplest interpretation: rename only in dim_accounts output, keep the alias consistent.

- [ ] **Create solutions/dim_accounts.sql** — dim_accounts with `a.account_status as customer_status` (replacing `a.account_status as account_status` or the bare `a.account_status`)
- [ ] **Create setup.sh** — `dbt run --select dim_accounts` (baseline — no changes needed, field exists as `account_status`)
- [ ] **Create solution.sh** — copy solution dim_accounts.sql, `dbt run --select dim_accounts`
- [ ] **Create tests/customer_status_in_dim_accounts.sql** — checks `customer_status` column exists

```sql
select 1
from {{ ref('dim_accounts') }}
where customer_status is not null
limit 0
```

- [ ] **Commit**

---

## Task 11: ops_pilot011 — Filter archived workspaces from int_account_workspaces (Type B)

> `int_account_workspaces` currently counts all workspaces including archived ones. Add a WHERE clause to exclude archived workspaces.

- [ ] **Create task.yaml** — difficulty: easy. Prompt: "The `int_account_workspaces` model is currently counting all workspaces, including archived ones. Modify it to exclude archived workspaces (where `workspace_status = 'archived'`) from the rollup. Rebuild with `dbt run --select int_account_workspaces+`."
- [ ] **Create solutions/int_account_workspaces.sql** — adds `where workspace_status != 'archived'` (or `where is_active_workspace`) after the FROM clause:

```sql
with workspaces as (
    select * from {{ ref('stg_workspaces') }}
    where workspace_status != 'archived'
)
select
    account_id,
    count(*) as workspace_count,
    ...
```

- [ ] **Create setup.sh** — `dbt run --select int_account_workspaces+` (baseline, no change)
- [ ] **Create solution.sh** — copy solution, `dbt run --select int_account_workspaces+`
- [ ] **Create tests/archived_workspaces_excluded.sql**

```sql
-- Verify no archived workspaces slip through: workspace_count should equal
-- active + sandbox (the only non-archived tiers in this dataset)
-- NOTE: validate against actual data when generating solution seeds —
-- if other non-archived statuses exist, adjust the comparison accordingly.
select account_id
from {{ ref('int_account_workspaces') }}
where active_workspace_count + sandbox_workspace_count != workspace_count
limit 1
```

- [ ] **Commit**

---

## Task 12: ops_pilot012 — active_workspace_count in mart_account_health (Type A)

- [ ] **Create task.yaml** — prompt: `mart_account_health` is missing `active_workspace_count`. Add it from the engagement data already joined in this model.
- [ ] **Create solutions/mart_account_health.sql** — correct version with `e.active_workspace_count`
- [ ] **Create setup.sh** — `sed -i '/    e.active_workspace_count,/d' models/marts/mart_account_health.sql && dbt run --select mart_account_health`
- [ ] **Create solution.sh** — copy, `dbt run --select mart_account_health`
- [ ] **Create tests/active_workspace_count_in_health.sql** — presence check
- [ ] **Commit**

---

## Task 13: ops_pilot013 — sandbox_workspace_count in dim_accounts (Type A)

- [ ] **Create task.yaml** — prompt: `dim_accounts` is missing `sandbox_workspace_count`. Add it from the workspace rollup data.
- [ ] **Create solutions/dim_accounts.sql** — correct version with `coalesce(w.sandbox_workspace_count, 0) as sandbox_workspace_count`
- [ ] **Create setup.sh** — `sed -i '/    coalesce(w.sandbox_workspace_count/d' models/marts/dim_accounts.sql && dbt run --select dim_accounts+`
- [ ] **Create solution.sh** — copy, `dbt run --select dim_accounts+`
- [ ] **Create tests/sandbox_workspace_count_in_dim_accounts.sql** — presence check
- [ ] **Commit**

---

## Task 14: ops_pilot014 — latest_invoice_status in mart_account_360 (Type A)

- [ ] **Create task.yaml** — prompt: `mart_account_360` is missing `latest_invoice_status`. Add it from the billing snapshot already joined in this model.
- [ ] **Create solutions/mart_account_360.sql** — correct version with `b.latest_invoice_status`
- [ ] **Create setup.sh** — `sed -i '/    b.latest_invoice_status,/d' models/marts/mart_account_360.sql && dbt run --select mart_account_360`
- [ ] **Create solution.sh** — copy, `dbt run --select mart_account_360`
- [ ] **Create tests/latest_invoice_status_in_360.sql** — presence check
- [ ] **Commit**

---

## Task 15: ops_pilot015 — latest_payment_status in int_account_billing_snapshot (Type A)

- [ ] **Create task.yaml** — prompt: `int_account_billing_snapshot` is missing `latest_payment_status`. Add it from the latest invoice data.
- [ ] **Create solutions/int_account_billing_snapshot.sql** — correct version with `li.latest_payment_status`
- [ ] **Create setup.sh** — `sed -i '/    li.latest_payment_status,/d' models/intermediate/int_account_billing_snapshot.sql && dbt run --select int_account_billing_snapshot+`
- [ ] **Create solution.sh** — copy, `dbt run --select int_account_billing_snapshot+`
- [ ] **Create tests/latest_payment_status_in_snapshot.sql** — presence check
- [ ] **Commit**

---

## Task 16: ops_pilot016 — gross_revenue_usd in int_monthly_revenue_prep (Type B)

> `gross_revenue_usd` does not currently exist. Define it as `subtotal_usd + tax_usd` (total billings before payment status).

- [ ] **Create task.yaml** — difficulty: easy. Prompt: "Add a `gross_revenue_usd` column to `int_monthly_revenue_prep`. This should represent the total billed amount including tax (subtotal plus tax) for each account-month, before accounting for payment status. Rebuild with `dbt run --select int_monthly_revenue_prep+`."
- [ ] **Create solutions/int_monthly_revenue_prep.sql** — adds `sum(f.subtotal_usd + f.tax_usd) as gross_revenue_usd` to the SELECT (alongside existing aggregations):

```sql
    sum(f.subtotal_usd) as subtotal_usd,
    sum(f.tax_usd) as tax_usd,
    sum(f.subtotal_usd + f.tax_usd) as gross_revenue_usd,
    sum(f.total_usd) as total_revenue_usd,
```

- [ ] **Create setup.sh** — `dbt run --select int_monthly_revenue_prep+` (no changes, baseline)
- [ ] **Create solution.sh** — copy solution, `dbt run --select int_monthly_revenue_prep+`
- [ ] **Create tests/gross_revenue_usd_in_revenue_prep.sql** — presence check + sanity check

```sql
-- Fails if gross_revenue_usd doesn't equal subtotal + tax
select 1
from {{ ref('int_monthly_revenue_prep') }}
where abs(gross_revenue_usd - (subtotal_usd + tax_usd)) > 0.01
limit 1
```

- [ ] **Commit**

---

## Task 17: ops_pilot017 — Exclude onboarding from recurring revenue (Type C)

> Currently `recurring_revenue_usd` in `int_invoice_finance` includes all lines where `is_recurring_line = true`. Onboarding line items (`line_type = 'onboarding'`) should be excluded even if flagged as recurring.

- [ ] **Create task.yaml** — difficulty: medium. Prompt: "In `int_invoice_finance`, the `recurring_revenue_usd` calculation currently includes onboarding line items (where `line_type = 'onboarding'`). Modify the calculation to exclude onboarding revenue from recurring revenue — onboarding charges should be treated as one-time even if flagged as recurring. Rebuild with `dbt run --select int_invoice_finance+`."
- [ ] **Create solutions/int_invoice_finance.sql** — changes the line_rollup CTE:

```sql
-- Change:
sum(case when is_recurring_line then line_amount_usd else 0 end) as recurring_revenue_usd,
-- To:
sum(case when is_recurring_line and line_type != 'onboarding' then line_amount_usd else 0 end) as recurring_revenue_usd,
```

- [ ] **Create setup.sh** — `dbt run --select int_invoice_finance+` (baseline — onboarding is included)
- [ ] **Create solution.sh** — copy solution, `dbt run --select int_invoice_finance+`
- [ ] **Create tests/onboarding_excluded_from_recurring.sql**

```sql
-- Verify recurring_revenue_usd + one_time_revenue_usd = base_subscription_revenue_usd + other items
-- Simple check: recurring + one_time should <= total subtotal per invoice
select invoice_id
from {{ ref('int_invoice_finance') }}
where recurring_revenue_usd + one_time_revenue_usd > subtotal_usd + 0.01
limit 1
```

- [ ] **Commit**

---

## Task 18: ops_pilot018 — one_time_revenue_usd in fct_monthly_revenue (Type A)

- [ ] **Create task.yaml** — prompt: `fct_monthly_revenue` is missing `one_time_revenue_usd`. Add it from the revenue prep data.
- [ ] **Create solutions/fct_monthly_revenue.sql** — correct version with `r.one_time_revenue_usd`
- [ ] **Create setup.sh** — `sed -i '/    r.one_time_revenue_usd,/d' models/marts/fct_monthly_revenue.sql && dbt run --select fct_monthly_revenue`
- [ ] **Create solution.sh** — copy, `dbt run --select fct_monthly_revenue`
- [ ] **Create tests/one_time_revenue_in_fct_monthly_revenue.sql** — presence check
- [ ] **Commit**

---

## Task 19: ops_pilot019 — has_past_due_invoice in mart_account_health (Type A)

- [ ] **Create task.yaml** — prompt: `mart_account_health` is missing `has_past_due_invoice`. Add it from the billing snapshot already joined in this model.
- [ ] **Create solutions/mart_account_health.sql** — correct version with `b.has_past_due_invoice`
- [ ] **Create setup.sh** — `sed -i '/    b.has_past_due_invoice,/d' models/marts/mart_account_health.sql && dbt run --select mart_account_health`
- [ ] **Create solution.sh** — copy, `dbt run --select mart_account_health`
- [ ] **Create tests/has_past_due_invoice_in_health.sql** — presence check
- [ ] **Commit**

---

## Task 20: ops_pilot020 — avg_active_users_7d in mart_account_360 (Type A)

- [ ] **Create task.yaml** — prompt: `mart_account_360` is missing `avg_active_users_7d`. Add it from the engagement data already joined.
- [ ] **Create solutions/mart_account_360.sql** — correct version with `e.avg_active_users_7d`
- [ ] **Create setup.sh** — `sed -i '/    e.avg_active_users_7d,/d' models/marts/mart_account_360.sql && dbt run --select mart_account_360`
- [ ] **Create solution.sh** — copy, `dbt run --select mart_account_360`
- [ ] **Create tests/avg_active_users_7d_in_360.sql** — presence check
- [ ] **Commit**

---

## Task 21: ops_pilot021 — total_api_calls_30d in mart_account_360 (Type A)

- [ ] **Create task.yaml** — prompt: `mart_account_360` is missing `total_api_calls_30d`. Add it from the engagement data.
- [ ] **Create solutions/mart_account_360.sql** — correct version with `e.total_api_calls_30d`
- [ ] **Create setup.sh** — `sed -i '/    e.total_api_calls_30d,/d' models/marts/mart_account_360.sql && dbt run --select mart_account_360`
- [ ] **Create solution.sh** — copy, `dbt run --select mart_account_360`
- [ ] **Create tests/total_api_calls_30d_in_360.sql** — presence check
- [ ] **Commit**

---

## Task 22: ops_pilot022 — open_ticket_count in mart_account_360 (Type A)

- [ ] **Create task.yaml** — prompt: `mart_account_360` is missing `open_ticket_count`. Add it from the support rollup CTE already computed in this model.
- [ ] **Create solutions/mart_account_360.sql** — correct version with `s.open_ticket_count`
- [ ] **Create setup.sh** — `sed -i '/    s.open_ticket_count,/d' models/marts/mart_account_360.sql && dbt run --select mart_account_360`
- [ ] **Create solution.sh** — copy, `dbt run --select mart_account_360`
- [ ] **Create tests/open_ticket_count_in_360.sql** — presence check
- [ ] **Commit**

---

## Task 23: ops_pilot023 — first_response_minutes in fct_support_tickets (Type A)

- [ ] **Create task.yaml** — prompt: `fct_support_tickets` is missing `first_response_minutes`. Add it from the SLA data.
- [ ] **Create solutions/fct_support_tickets.sql** — correct version with `s.first_response_minutes`
- [ ] **Create setup.sh** — `sed -i '/    s.first_response_minutes,/d' models/marts/fct_support_tickets.sql && dbt run --select fct_support_tickets`
- [ ] **Create solution.sh** — copy, `dbt run --select fct_support_tickets`
- [ ] **Create tests/first_response_minutes_in_fct_support_tickets.sql** — presence check
- [ ] **Commit**

---

## Task 24: ops_pilot024 — plan_name in fct_support_tickets (Type A)

- [ ] **Create task.yaml** — prompt: `fct_support_tickets` is missing `plan_name`. Add it from the account billing snapshot data that is already joined in this model.
- [ ] **Create solutions/fct_support_tickets.sql** — correct version with `b.plan_name`
- [ ] **Create setup.sh** — `sed -i '/    b.plan_name,/d' models/marts/fct_support_tickets.sql && dbt run --select fct_support_tickets`
- [ ] **Create solution.sh** — copy, `dbt run --select fct_support_tickets`
- [ ] **Create tests/plan_name_in_fct_support_tickets.sql** — presence check
- [ ] **Commit**

---

## Task 25: ops_pilot025 — is_primary in int_workspace_roster (Type A)

- [ ] **Create task.yaml** — prompt: `int_workspace_roster` is missing the `is_primary` flag indicating whether the workspace is the primary workspace for the account. Add it from the workspace data already joined in this model.
- [ ] **Create solutions/int_workspace_roster.sql** — correct version with `w.is_primary`
- [ ] **Create setup.sh** — `sed -i '/    w.is_primary,/d' models/intermediate/int_workspace_roster.sql && dbt run --select int_workspace_roster`
- [ ] **Create solution.sh** — copy, `dbt run --select int_workspace_roster`
- [ ] **Create tests/is_primary_in_int_workspace_roster.sql** — presence check
- [ ] **Commit**

---

## Final Verification

After all 25 tasks are created:

- [ ] **Smoke test one task end-to-end with sage agent:**

```bash
cd /Users/joel/Documents/GitHub/ade-bench
uv run scripts_python/run_harness.py --agent sage --task-ids ops_pilot001 --no-rebuild
```

Expected: PASS

- [ ] **Verify setup.sh actually breaks the build:**

```bash
# Manually test setup
cd /tmp/test-ops-pilot
# copy project, run setup.sh, check dbt run still works but column is gone
```

- [ ] **Generate solution seeds for key tasks:**

```bash
ade run ops_pilot001 ops_pilot016 ops_pilot017 --agent sage --db duckdb --project-type dbt --seed
```

- [ ] **Final commit with all 25 tasks:**

```bash
git add tasks/ops_pilot0*/
git commit -m "feat(ops_pilot): add 25 benchmark tasks (ops_pilot001-025)"
```

---

## Key Reference Files

- Shared project models: `shared/projects/dbt/ops_pilot/models/`
- Existing task examples: `tasks/airbnb001/`, `tasks/analytics_engineering002/`
- CONTRIBUTING.md: `docs/CONTRIBUTING.md`
- Task template: `tasks/.template/task.yaml`
