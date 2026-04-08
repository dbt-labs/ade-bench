#!/bin/bash
if [[ "$*" == *"--db-type=snowflake"* ]]; then
    patch -p1 < /sage/solutions/changes.snowflake.patch
else
    patch -p1 < /sage/solutions/changes.patch
fi
dbt seed --select sla_response_targets
dbt run --select int_support_sla fct_support_tickets
