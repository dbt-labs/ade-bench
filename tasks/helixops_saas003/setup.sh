#!/bin/bash
patch -p1 < /app/setup/changes.patch
dbt run --select stg_workspaces int_workspace_daily_metrics int_account_daily_usage
