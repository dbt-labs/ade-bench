#!/bin/bash
SOLUTIONS_DIR="$(dirname "$(readlink -f "${BASH_SOURCE}")")/solutions"
cp "$SOLUTIONS_DIR/stg_workspaces.sql" models/staging/stg_workspaces.sql
dbt run --select stg_workspaces int_account_workspaces dim_accounts
