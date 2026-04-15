#!/bin/bash

file="analysis__lap_times.sql"

SETUP_DIR="$(dirname "$(readlink -f "${BASH_SOURCE}")")/setup"
cp $SETUP_DIR/$file models/stats/$file

dbt run

