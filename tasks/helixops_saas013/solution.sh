#!/bin/bash
set -euo pipefail
patch -p1 < /sage/solutions/changes.patch

set +euo pipefail
dbt run --select stg_invoice_line_items+
exit 0
