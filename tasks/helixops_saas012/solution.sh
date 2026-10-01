#!/bin/bash
set -euo pipefail
patch -p1 < /sage/solutions/changes.patch

set +euo pipefail
dbt run --select fct_monthly_revenue
exit 0
