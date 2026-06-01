#!/bin/bash
set -euo pipefail
# Create the product_performance model
cat > models/foo.sql << EOF
select 1;
EOF

dbt deps

# Run dbt to create the models
dbt run --select foo
