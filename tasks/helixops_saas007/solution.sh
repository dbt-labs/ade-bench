#!/bin/bash
set -euo pipefail
patch -p1 < /sage/solutions/changes.patch

set +euo pipefail
dbt run --select int_account_billing_snapshot mart_account_360 mart_account_health
