#!/bin/bash
set -euo pipefail
# Department already exists in int_workspace_roster - no changes needed
dbt run --select int_workspace_roster
