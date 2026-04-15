#!/bin/bash
set -euo pipefail
## Copy snapshot, staging, and analytical model files
patch -p1 < /sage/solutions/changes.patch

if [[ "$*" == *"--db-type=snowflake"* ]]; then
    patch -p1 < /sage/solutions/changes.snowflake.patch
fi

mkdir -p snapshots

# Run snapshot then models
dbt snapshot
dbt run
