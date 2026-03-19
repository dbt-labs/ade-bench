#!/bin/bash
SOLUTIONS_DIR="$(dirname "$(readlink -f "${BASH_SOURCE}")")/solutions"
cp "$SOLUTIONS_DIR/int_workspace_roster.sql" models/intermediate/int_workspace_roster.sql
dbt run --select int_workspace_roster
