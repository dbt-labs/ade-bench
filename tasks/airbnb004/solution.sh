#!/bin/bash
## Add the primary key to the fct_reviews model
patch -p1 < /sage/solutions/changes.patch

if [[ "$*" == *"--db-type=snowflake"* ]]; then
    patch -p1 < /sage/solutions/changes.snowflake.patch
fi

# Run dbt to create the models
dbt run --select fct_reviews --full-refresh
