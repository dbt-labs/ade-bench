#!/bin/bash
set -euo pipefail

## remove old models
rm -r models/agg
rm -r models/dim
rm -r models/fact

## Add schema.yml to models directory
SETUP_DIR="$(dirname "$(readlink -f "${BASH_SOURCE}")")/setup"

cp $SETUP_DIR/schema.yml models/schema.yml

dbt deps