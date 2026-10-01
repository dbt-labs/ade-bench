#!/bin/bash
set -euo pipefail

## Fix the error by changing the data type of the underlying table.

## Get the schema based on the database type.
if [[ "$*" == *"--db-type=duckdb"* ]]; then
    schema='main'
else
    schema='public'
fi

# Execute SQL using the run_sql utility.
/scripts/run_sql.sh "$@" << SQL
-- Update the id field to be a string.
create or replace table ${schema}.task_data_temp as
  select
    * replace (due_at::timestamp as due_at)
  from ${schema}.task_data;

-- Rename the table to the original name.
drop table ${schema}.task_data;
alter table ${schema}.task_data_temp rename to task_data;
SQL

## Copy solution files
patch -p1 < /sage/solutions/changes.patch
