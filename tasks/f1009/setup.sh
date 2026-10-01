#!/bin/bash
set -euo pipefail

# Run dbt to create the models
dbt deps && dbt run
