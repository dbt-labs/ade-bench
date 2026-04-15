#!/bin/bash
set -euo pipefail
# Create the product_performance and daily_shop_performance models
patch -p1 < /sage/solutions/changes.patch

set +euo pipefail

dbt deps

# Run dbt to create the models
dbt run --select product_performance daily_shop_performance
exit 0
