#!/bin/bash
set -euo pipefail
patch -p1 < /sage/solutions/changes.patch
dbt run --select fct_monthly_revenue
