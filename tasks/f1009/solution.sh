#!/bin/bash
set -euo pipefail

file="analysis__drivers_current_age.sql"

SOLUTIONS_DIR="$(dirname "$(readlink -f "${BASH_SOURCE}")")/solutions"
cp $SOLUTIONS_DIR/$file models/stats/$file

dbt run --select analysis__drivers_current_age

