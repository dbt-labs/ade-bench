#!/bin/bash
set -euo pipefail

# Remove all intermediate models
rm -r models/intermediate
rm -r models/*

dbt deps
dbt run