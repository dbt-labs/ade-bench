#!/bin/bash
## Restore src_* model references and update f1_dataset.yml
if [[ "$*" == *"--db-type=snowflake"* ]]; then
    patch -p1 < /sage/solutions/changes.snowflake.patch
else
    patch -p1 < /sage/solutions/changes.duckdb.patch
fi
