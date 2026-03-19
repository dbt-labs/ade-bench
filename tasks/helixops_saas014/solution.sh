#!/bin/bash
SOLUTIONS_DIR="$(dirname "$(readlink -f "${BASH_SOURCE}")")/solutions"
cp "$SOLUTIONS_DIR/stg_workspace_usage_daily.sql" models/staging/stg_workspace_usage_daily.sql
cp "$SOLUTIONS_DIR/int_workspace_daily_metrics.sql" models/intermediate/int_workspace_daily_metrics.sql
cp "$SOLUTIONS_DIR/int_account_daily_usage.sql" models/intermediate/int_account_daily_usage.sql
cp "$SOLUTIONS_DIR/int_account_engagement.sql" models/intermediate/int_account_engagement.sql
cp "$SOLUTIONS_DIR/fct_daily_account_usage.sql" models/marts/fct_daily_account_usage.sql
cp "$SOLUTIONS_DIR/mart_account_360.sql" models/marts/mart_account_360.sql
cp "$SOLUTIONS_DIR/mart_account_health.sql" models/marts/mart_account_health.sql
dbt run --select stg_workspace_usage_daily+
