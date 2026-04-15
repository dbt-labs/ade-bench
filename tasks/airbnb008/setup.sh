#!/bin/bash
set -euo pipefail

## Add broken agg.yml to agg directory
SETUP_DIR="$(dirname "$(readlink -f "${BASH_SOURCE}")")/setup"

if [[ "$*" == *"--project-type=dbt-fusion"* ]]; then
    echo "Using dbt-fusion compatible schema file"
    # Use dbt-fusion compatible schema file
    cp $SETUP_DIR/agg.dbtf.yml models/agg/agg.yml
else
    cp $SETUP_DIR/agg.yml models/agg/agg.yml
fi