#!/bin/bash
set -euo pipefail
patch -p1 < /app/setup/changes.patch

dbt deps
dbt run
