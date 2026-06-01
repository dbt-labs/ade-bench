#!/bin/bash
set -euo pipefail

## Run deps before modifying files
dbt deps
dbt run