#!/bin/bash
SOLUTIONS_DIR="$(dirname "$(readlink -f "${BASH_SOURCE}")")/solutions"

## Update schema config in solution files by db type
if [[ "$*" == *"--db-type=duckdb"* ]]; then
    replace='schema="main"'
else
    replace='schema="public"'
fi

for file in src_hosts.sql dim_superhost_evolution.sql; do
    find='schema="main"'
    sed -i "s/${find}/${replace}/g" "$SOLUTIONS_DIR/$file"
done

# Copy snapshot definition
mkdir -p snapshots
cp "$SOLUTIONS_DIR/snap__hosts.sql" snapshots/snap__hosts.sql

# Copy modified staging model (overwrites existing)
cp "$SOLUTIONS_DIR/src_hosts.sql" models/source/src_hosts.sql

# Copy analytical model
cp "$SOLUTIONS_DIR/dim_superhost_evolution.sql" models/dim/dim_superhost_evolution.sql

# Run snapshot then models
dbt snapshot
dbt run
