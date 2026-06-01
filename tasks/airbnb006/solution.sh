#!/bin/bash
set -euo pipefail

## Fix CTE names in fct_reviews and dim_hosts
patch -p1 < /sage/solutions/changes.patch

set +euo pipefail

dbt deps
exit 0
