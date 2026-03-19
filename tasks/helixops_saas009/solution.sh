#!/bin/bash
SOLUTIONS_DIR="$(dirname "$(readlink -f "${BASH_SOURCE}")")/solutions"
cp "$SOLUTIONS_DIR/dim_accounts_v2.sql" models/marts/dim_accounts_v2.sql
dbt run --select dim_accounts_v2
