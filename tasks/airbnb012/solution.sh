#!/bin/bash
SOLUTIONS_DIR="$(dirname "$(readlink -f "${BASH_SOURCE}")")/solutions"

# Copy fixed NPS models (corrects integer division bug) and unit tests
cp "$SOLUTIONS_DIR/listing_agg_nps_reviews.sql" models/agg/listing_agg_nps_reviews.sql
cp "$SOLUTIONS_DIR/daily_agg_nps_reviews.sql" models/agg/daily_agg_nps_reviews.sql
cp "$SOLUTIONS_DIR/nps_unit_tests.yml" models/agg/nps_unit_tests.yml

dbt run --select listing_agg_nps_reviews daily_agg_nps_reviews
