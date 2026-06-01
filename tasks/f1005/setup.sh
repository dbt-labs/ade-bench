#!/bin/bash
set -euo pipefail
patch -p1 < /app/setup/changes.patch

set +euo pipefail

# Run dbt to create the models
dbt deps
dbt run
exit 0
