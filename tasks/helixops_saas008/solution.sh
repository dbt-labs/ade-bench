#!/bin/bash
SOLUTIONS_DIR="$(dirname "$(readlink -f "${BASH_SOURCE}")")/solutions"
cp "$SOLUTIONS_DIR/stg_accounts.sql" models/staging/stg_accounts.sql
cp "$SOLUTIONS_DIR/dim_accounts.sql" models/marts/dim_accounts.sql
cp "$SOLUTIONS_DIR/mart_account_360.sql" models/marts/mart_account_360.sql
cp "$SOLUTIONS_DIR/mart_account_health.sql" models/marts/mart_account_health.sql
dbt run --select stg_accounts+
