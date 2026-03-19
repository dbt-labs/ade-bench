#!/bin/bash
SOLUTIONS_DIR="$(dirname "$(readlink -f "${BASH_SOURCE}")")/solutions"
cp "$SOLUTIONS_DIR/fct_monthly_revenue.sql" models/marts/fct_monthly_revenue.sql
rm -f models/intermediate/int_monthly_revenue_prep.sql
dbt run --select fct_monthly_revenue
