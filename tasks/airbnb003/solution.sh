#!/bin/bash
# Update source models to be views
if [[ "$*" == *"--db-type=snowflake"* ]]; then
    patch -p1 < /sage/solutions/changes.snowflake.patch
else
    patch -p1 < /sage/solutions/changes.duckdb.patch
fi
