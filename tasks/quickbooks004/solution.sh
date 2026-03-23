#!/bin/bash
## Add using_exchange_rate variable and wrap exchange rate columns
if [[ "$*" == *"--db-type=snowflake"* ]]; then
    patch -p1 < /sage/solutions/changes.snowflake.patch
else
    patch -p1 < /sage/solutions/changes.duckdb.patch
fi
