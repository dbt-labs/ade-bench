#!/bin/bash

# Update the "products" source table to change the id field to a string, and add several new rows that have ids as hashes.
## Get the schema based on the database type.
if [[ "$*" == *"--db-type=duckdb"* ]]; then
    schema='main'
else
    schema='public'
fi

## Run the query to duplicate rows
/scripts/run_sql.sh "$@" << SQL
-- Update the id field to be a string.
create or replace table ${schema}.products_temp as
  select
    * replace (id::varchar as id)
  from ${schema}.products;

-- Add several new rows that have ids as hashes.
insert into ${schema}.products_temp
  select
    * replace (md5(id) as id)
  from ${schema}.products_temp
  where id::int >= 60 and id::int <= 80;

-- Rename the table to the original name.
drop table ${schema}.products;
alter table ${schema}.products_temp rename to products;
SQL

dbt deps
dbt run