#!/bin/bash
SOLUTIONS_DIR="$(dirname "$(readlink -f "${BASH_SOURCE}")")/solutions"
cp "$SOLUTIONS_DIR/stg_workspaces.sql" models/staging/stg_workspaces.sql
cp "$SOLUTIONS_DIR/int_workspace_daily_metrics.sql" models/intermediate/int_workspace_daily_metrics.sql
dbt run --select stg_workspaces int_workspace_daily_metrics int_account_daily_usage
