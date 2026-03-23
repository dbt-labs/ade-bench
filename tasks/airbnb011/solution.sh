#!/bin/bash
## Copy snapshot, staging, and analytical model files
if [[ "$*" == *"--db-type=snowflake"* ]]; then
    patch -p1 < /sage/solutions/changes.snowflake.patch
else
    patch -p1 < /sage/solutions/changes.duckdb.patch
fi

mkdir -p snapshots

# Run snapshot then models
dbt snapshot
dbt run
