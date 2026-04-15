#!/bin/bash

## Introduce an error by changing the data type of the underlying table.

## Get the schema based on the database type.
if [[ "$*" == *"--db-type=duckdb"* ]]; then
    schema='main'
    due_at='due_at'
else
    schema='public'
    due_at='null'
fi

# Execute SQL using the run_sql utility.
/scripts/run_sql.sh "$@" << SQL
-- Update the id field to be a string.
create or replace table ${schema}.task_data_temp as
  select
    * replace (${due_at}::integer as due_at)
  from ${schema}.task_data;

-- Rename the table to the original name.
drop table ${schema}.task_data;
alter table ${schema}.task_data_temp rename to task_data;
SQL

## Run the dbt project.
dbt deps
dbt run