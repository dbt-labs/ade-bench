#!/bin/bash
SOLUTIONS_DIR="$(dirname "$(readlink -f "${BASH_SOURCE}")")/solutions"
cp "$SOLUTIONS_DIR/int_account_workspaces.sql" models/intermediate/int_account_workspaces.sql
dbt run --select int_account_workspaces
