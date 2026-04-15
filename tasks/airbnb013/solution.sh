#!/bin/bash
set -euo pipefail
SOLUTIONS_DIR="$(dirname "$(readlink -f "${BASH_SOURCE}")")/solutions"

cp "$SOLUTIONS_DIR/fct_reviews.sql" models/fact/fct_reviews.sql
