#!/bin/bash

if [[ "$*" == *"--db-type=duckdb"* ]]; then
    schema='main'
else
    schema='public'
fi

/scripts/run_sql.sh "$@" << SQL
UPDATE ${schema}.raw_invoice_line_items
SET recurring_hint = 'Y'
WHERE line_id IN ('L7102', 'L7220', 'L7342');
SQL

dbt run
