#!/bin/bash
set -euo pipefail
patch -p1 --batch < /app/setup/changes.patch || true

if [[ "$*" == *"--db-type=snowflake"* ]]; then
    patch -p1 --batch --forward < /app/setup/changes.snowflake.patch
fi

set +euo pipefail

dbt deps
dbt run
exit 0
