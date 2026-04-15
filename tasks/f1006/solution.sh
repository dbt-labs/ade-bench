#!/bin/bash
set -euo pipefail
## Change sum back to max in constructor_points and driver_points
patch -p1 < /sage/solutions/changes.patch

set +euo pipefail

# Run dbt to create the models
dbt run --select constructor_points driver_points
