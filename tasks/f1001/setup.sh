#!/bin/bash

## Remove sources
rm models/core/*.sql

models=(
  "circuits"
  "constructor_results"
  "constructor_standings"
  "constructors"
  "driver_standings"
  "drivers"
  "lap_times"
  "pit_stops"
  "qualifying"
  "races"
  "results"
  "seasons"
  "status"
)

if [[ "$OSTYPE" == "darwin"* ]]; then
  SED_CMD=(sed -i '')
else
  SED_CMD=(sed -i)
fi

for model in "${models[@]}"; do
  replace="ref('src_${model}')/ref('${model}')"
  path="models/staging/f1_dataset/stg_f1_dataset__${model}.sql"
  
  "${SED_CMD[@]}" "s/${replace}/g" "${path}"
done

## One-off updates to models
"${SED_CMD[@]}" "s/ref('src_status')/ref('status')/g" "models/staging/f1_dataset/stg_f1_dataset__results.sql"
"${SED_CMD[@]}" "s/ref('src_position_descriptions')/ref('position_descriptions')/g" "models/staging/f1_dataset/stg_f1_dataset__results.sql"
"${SED_CMD[@]}" "s/ref('src_position_descriptions')/ref('position_descriptions')/g" "models/stats/most_races.sql"

##Remove stuff from cofig
cat > models/core/f1_dataset.yml << 'EOF'
version: 2

sources:
  - name: f1_dataset
    schema: main
    tables:
      - name: circuits
      - name: constructors
      - name: constructor_standings
      - name: constructor_results
      - name: drivers
      - name: driver_standings
      - name: lap_times
      - name: pit_stops
      - name: qualifying
      - name: races
      - name: results
      - name: seasons
      - name: status
EOF