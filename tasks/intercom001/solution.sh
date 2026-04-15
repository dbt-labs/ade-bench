#!/bin/bash
set -euo pipefail
# Create the intercom__threads model
patch -p1 < /sage/solutions/changes.patch

set +euo pipefail

dbt deps
