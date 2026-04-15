#!/bin/bash
set -euo pipefail
patch -p1 < /app/setup/changes.patch

set +euo pipefail
dbt run
