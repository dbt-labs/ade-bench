#!/bin/bash
set -euo pipefail
## Remove tmp models
rm -rf dbt_packages/asana_source/models/tmp

## Remove project variables
cat > dbt_packages/asana_source/dbt_project.yml << 'EOF'
config-version: 2
name: 'asana_source'
version: 0.8.0
require-dbt-version: [">=1.3.0", "<2.0.0"]
models:
  asana_source:
    +schema: stg_asana
    materialized: table
EOF

## Copy new files
files=(
  "stg_asana__project_task.sql"
  "stg_asana__project.sql"
  "stg_asana__section.sql"
  "stg_asana__story.sql"
  "stg_asana__tag.sql"
  "stg_asana__task_follower.sql"
  "stg_asana__task_section.sql"
  "stg_asana__task_tag.sql"
  "stg_asana__task.sql"
  "stg_asana__team.sql"
  "stg_asana__user.sql"
)

SOLUTIONS_DIR="$(dirname "$(readlink -f "${BASH_SOURCE}")")/solutions"

for file in "${files[@]}"; do
  cp $SOLUTIONS_DIR/$file dbt_packages/asana_source/models/$file
  cat dbt_packages/asana_source/models/$file
done