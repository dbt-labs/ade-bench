#!/bin/bash
set -euo pipefail
## Fix position_desc case sensitivity in finishes_by_driver
patch -p1 < /sage/solutions/changes.patch

set +euo pipefail

# Run dbt to create the models
dbt run --select finishes_by_driver
