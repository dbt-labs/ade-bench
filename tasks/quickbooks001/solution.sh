#!/bin/bash

## Solution: Override Fivetran staging models to handle unix epoch timestamps.
## Instead of modifying the underlying data, we create custom versions of the
## staging models that convert the epoch integers back to proper dates.

# Get the directory where this script is located
SCRIPT_DIR="$(dirname "$(readlink -f "${BASH_SOURCE}")")"

# Disable the package models in dbt_project.yml
yq -i '.models.quickbooks_source.stg_quickbooks__refund_receipt."+enabled" = false' dbt_project.yml
yq -i '.models.quickbooks_source.stg_quickbooks__sales_receipt."+enabled" = false' dbt_project.yml
yq -i '.models.quickbooks_source.stg_quickbooks__estimate."+enabled" = false' dbt_project.yml

# Create staging directory if it doesn't exist
mkdir -p models/staging

# Copy our override models that handle the epoch-to-date conversion
cp $SCRIPT_DIR/solutions/stg_quickbooks__refund_receipt.sql models/staging/
cp $SCRIPT_DIR/solutions/stg_quickbooks__sales_receipt.sql models/staging/
cp $SCRIPT_DIR/solutions/stg_quickbooks__estimate.sql models/staging/
