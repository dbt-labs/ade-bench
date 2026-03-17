#!/bin/bash

SETUP_DIR="$(dirname "$(readlink -f "${BASH_SOURCE}")")/setup"

# Copy inject script to /tmp (setup/ is removed after setup.sh runs)
cp "$SETUP_DIR/inject_reviews.py" /tmp/inject_reviews.py

dbt deps
dbt run

# Inject 5 reviews on the current max date
python3 /tmp/inject_reviews.py

# Run incrementally — creates the broken state (5 injected reviews are dropped)
dbt run --select fct_reviews

echo "Setup complete. fct_reviews is now missing the 5 injected reviews."
