#!/bin/bash
set -euo pipefail
SOLUTIONS_DIR="$(dirname "$(readlink -f "${BASH_SOURCE}")")/solutions"

if [[ "$*" == *"--project-type=dbt-fusion"* ]]; then
    # Use dbt-fusion compatible schema file
    echo "Using dbt-fusion compatible schema file"
    cp $SOLUTIONS_DIR/agg.dbtf.yml models/agg/agg.yml
else
    cp $SOLUTIONS_DIR/agg.yml models/agg/agg.yml
fi