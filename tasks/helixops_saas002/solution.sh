#!/bin/bash
SOLUTIONS_DIR="$(dirname "$(readlink -f "${BASH_SOURCE}")")/solutions"
cp "$SOLUTIONS_DIR/dim_accounts.sql" models/marts/dim_accounts.sql
cp "$SOLUTIONS_DIR/mart_account_360.sql" models/marts/mart_account_360.sql
dbt run --select dim_accounts mart_account_360
