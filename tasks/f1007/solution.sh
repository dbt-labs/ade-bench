#!/bin/bash
set -euo pipefail
## Fix the left join
SOLUTIONS_DIR="$(dirname "$(readlink -f "${BASH_SOURCE}")")/solutions"

file="stg_f1_dataset__results.sql"
cp $SOLUTIONS_DIR/$file models/staging/f1_dataset/stg_f1_dataset__results.sql

dbt run