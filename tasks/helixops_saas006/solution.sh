#!/bin/bash
SOLUTIONS_DIR="$(dirname "$(readlink -f "${BASH_SOURCE}")")/solutions"
cp "$SOLUTIONS_DIR/mart_account_360.sql" models/marts/mart_account_360.sql
dbt run --select mart_account_360
