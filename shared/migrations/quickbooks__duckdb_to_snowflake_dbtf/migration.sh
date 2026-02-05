#!/bin/bash

# Update primary schema in dbt_project.yml file
yq -i '.vars.quickbooks_schema = "public"' dbt_project.yml

# Copy Snowflake-specific solution models that handle epoch-to-timestamp conversion
MIGRATION_DIR="$(dirname "$(readlink -f "${BASH_SOURCE}")")"
cp $MIGRATION_DIR/solutions/stg_quickbooks__refund_receipt.sql solutions/
cp $MIGRATION_DIR/solutions/stg_quickbooks__sales_receipt.sql solutions/
cp $MIGRATION_DIR/solutions/stg_quickbooks__estimate.sql solutions/
