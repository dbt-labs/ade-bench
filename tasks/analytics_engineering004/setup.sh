#!/bin/bash
set -euo pipefail

# Remove the obt_product_inventory model
rm models/analytics_obt/obt_product_inventory.sql

dbt deps
dbt run