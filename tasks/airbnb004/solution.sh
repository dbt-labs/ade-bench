#!/bin/bash
## Add the primary key to the fct_reviews model
if [[ "$*" == *"--db-type=snowflake"* ]]; then
    patch -p1 < /sage/solutions/changes.snowflake.patch
else
    patch -p1 < /sage/solutions/changes.duckdb.patch
fi

# Run dbt to create the models
dbt run --select fct_reviews --full-refresh
