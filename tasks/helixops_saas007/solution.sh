#!/bin/bash
SOLUTIONS_DIR="$(dirname "$(readlink -f "${BASH_SOURCE}")")/solutions"
cp "$SOLUTIONS_DIR/int_account_billing_snapshot.sql" models/intermediate/int_account_billing_snapshot.sql
cp "$SOLUTIONS_DIR/mart_account_360.sql" models/marts/mart_account_360.sql
cp "$SOLUTIONS_DIR/mart_account_health.sql" models/marts/mart_account_health.sql
dbt run --select int_account_billing_snapshot mart_account_360 mart_account_health
