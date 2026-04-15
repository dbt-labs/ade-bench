#!/bin/bash
set -euo pipefail
## Add using_exchange_rate variable and wrap exchange rate columns
yq -i '.vars.quickbooks.using_exchange_rate = false' dbt_project.yml

patch -p1 < /sage/solutions/changes.patch

if [[ "$*" == *"--db-type=snowflake"* ]]; then
    patch -p1 < /sage/solutions/changes.snowflake.patch
fi

set +euo pipefail

dbt run
exit 0
