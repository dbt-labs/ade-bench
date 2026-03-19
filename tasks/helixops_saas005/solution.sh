#!/bin/bash
SOLUTIONS_DIR="$(dirname "$(readlink -f "${BASH_SOURCE}")")/solutions"
cp "$SOLUTIONS_DIR/stg_users.sql" models/staging/stg_users.sql
dbt run --select stg_users+
