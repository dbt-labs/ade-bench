#!/bin/bash
set -euo pipefail

s1="analysis__lap_times.sql"
s2="analysis__lap_times_exclude_pit_stops.sql"

SOLUTIONS_DIR="$(dirname "$(readlink -f "${BASH_SOURCE}")")/solutions"

cp $SOLUTIONS_DIR/$s1 models/stats/$s1
cp $SOLUTIONS_DIR/$s2 models/stats/$s2

dbt run --select analysis__lap_times analysis__lap_times_exclude_pit_stops

