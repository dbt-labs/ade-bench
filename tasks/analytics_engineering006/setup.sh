#!/bin/bash
set -euo pipefail

# Remove the models that need to be created.
rm models/analytics_obt/obt_product_inventory.sql
rm models/warehouse/dim_products.sql
rm models/warehouse/fact_inventory.sql

# Remove the obt_sales_overview model, which depends on removed models.
rm models/analytics_obt/obt_sales_overview.sql

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

dbt deps
dbt run