#!/bin/bash
set -euo pipefail
## Fix the dates_cte filter in mom_agg_reviews
patch -p1 < /sage/solutions/changes.patch

set +euo pipefail

# Run dbt to create the models
dbt run --select mom_agg_reviews --full-refresh
exit 0
