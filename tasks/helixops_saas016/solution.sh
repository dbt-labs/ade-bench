#!/bin/bash
set -euo pipefail
patch -p1 < /sage/solutions/changes.patch

set +euo pipefail
dbt seed --select sla_enterprise_targets
dbt run --select int_support_sla fct_support_tickets
exit 0
