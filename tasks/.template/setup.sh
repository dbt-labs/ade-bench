#!/bin/bash
set -euo pipefail

dbt deps
dbt run