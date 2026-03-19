#!/bin/bash
SOLUTIONS_DIR="$(dirname "$(readlink -f "${BASH_SOURCE}")")/solutions"
cp "$SOLUTIONS_DIR/sla_response_targets.csv" seeds/sla_response_targets.csv
cp "$SOLUTIONS_DIR/int_support_sla.sql" models/intermediate/int_support_sla.sql
dbt seed --select sla_response_targets
dbt run --select int_support_sla fct_support_tickets
