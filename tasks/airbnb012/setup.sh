#!/bin/bash
set -euo pipefail

SETUP_DIR="$(dirname "$(readlink -f "${BASH_SOURCE}")")/setup"

# Copy NPS models into project (they don't exist in shared project by default)
cp "$SETUP_DIR/daily_agg_nps_reviews.sql" models/agg/daily_agg_nps_reviews.sql
cp "$SETUP_DIR/listing_agg_nps_reviews.sql" models/agg/listing_agg_nps_reviews.sql

# Copy evaluation scripts to /tmp (setup/ is removed after setup.sh runs)
cp "$SETUP_DIR/check_unit_tests.py" /tmp/check_unit_tests.py
cp "$SETUP_DIR/run_broken_model_tests.py" /tmp/run_broken_model_tests.py
cp -r "$SETUP_DIR/broken" /tmp/broken

# Build the project so the agent has a working state to start from
dbt deps
dbt run
