#!/bin/bash
set -euo pipefail

## Create duplicates in the inventory table
## Get the schema based on the database type.
if [[ "$*" == *"--db-type=duckdb"* ]]; then
    schema='main'
else
    schema='public'
fi

## Run the query to duplicate rows
/scripts/run_sql.sh "$@" << SQL
insert into ${schema}.inventory_transactions
    select *
    from ${schema}.inventory_transactions
    where mod(product_id,2) = 0;
SQL


## Replace the fact_inventory model with a version that doesn't handle duplicates
patch -p1 < /app/setup/changes.patch

set +euo pipefail

dbt deps
dbt run
