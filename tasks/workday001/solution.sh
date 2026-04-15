#!/bin/bash
set -euo pipefail
# Create the foo model
patch -p1 < /sage/solutions/changes.patch

# Run dbt to create the models
dbt run --select foo
