#!/bin/bash

## Introduce an error by converting date columns to unix epoch integers.

## Get the schema and epoch function based on the database type.
## Using created_at column to populate the date columns because the sample data is null
## and I need something realistic for the agent to work with.
if [[ "$*" == *"--db-type=duckdb"* ]]; then
    schema='main'
    # DuckDB: epoch() returns seconds since 1970-01-01
    epoch_txn_date='epoch(created_at)::integer'
    epoch_due_date='epoch(created_at)::integer'
else
    schema='public'
    # Snowflake: DATEDIFF to get seconds since epoch
    epoch_txn_date="DATEDIFF('second', '1970-01-01'::timestamp, created_at::timestamp)::integer"
    epoch_due_date="DATEDIFF('second', '1970-01-01'::timestamp, created_at::timestamp)::integer"
fi

/scripts/run_sql.sh "$@" << SQL
create or replace table ${schema}.refund_receipt_data_temp as
  select * replace (${epoch_txn_date} as transaction_date)
  from ${schema}.refund_receipt_data;

create or replace table ${schema}.sales_receipt_data_temp as
  select * replace (${epoch_txn_date} as transaction_date)
  from ${schema}.sales_receipt_data;

create or replace table ${schema}.estimate_data_temp as
  select * replace (${epoch_due_date} as due_date)
  from ${schema}.estimate_data;

drop table ${schema}.sales_receipt_data;
drop table ${schema}.refund_receipt_data;
drop table ${schema}.estimate_data;

alter table ${schema}.sales_receipt_data_temp rename to sales_receipt_data;
alter table ${schema}.refund_receipt_data_temp rename to refund_receipt_data;
alter table ${schema}.estimate_data_temp rename to estimate_data;
SQL

## Run the dbt project.
dbt deps
DBT_STATIC_ANALYSIS=off dbt run