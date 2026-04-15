#!/bin/bash
set -euo pipefail
patch -p1 < /sage/solutions/changes.patch

set +euo pipefail
dbt run --select stg_workspaces int_workspace_daily_metrics int_account_daily_usage
