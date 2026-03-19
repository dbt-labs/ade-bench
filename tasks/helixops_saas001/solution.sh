#!/bin/bash
SOLUTIONS_DIR="$(dirname "$(readlink -f "${BASH_SOURCE}")")/solutions"
cp "$SOLUTIONS_DIR/dim_accounts.sql" models/marts/dim_accounts.sql
dbt run --select dim_accounts
