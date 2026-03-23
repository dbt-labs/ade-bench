#!/bin/bash

SETUP_DIR="$(dirname "$(readlink -f "${BASH_SOURCE}")")/setup"

# Copy inject script to /tmp (setup/ is removed after setup.sh runs)
cp "$SETUP_DIR/inject_reviews.py" /tmp/inject_reviews.py
cp "$SETUP_DIR/new_reviews.csv" /tmp/new_reviews.csv

dbt deps
dbt run
python3 /tmp/inject_reviews.py
dbt run --select src_reviews
dbt run --select fct_reviews

echo "Setup complete. fct_reviews is now missing the 5 injected reviews."
