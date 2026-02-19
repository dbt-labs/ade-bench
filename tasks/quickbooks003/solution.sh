#!/bin/bash



## Remove the using_department variable
if [[ "$OSTYPE" == "darwin"* ]]; then
  SED_CMD=(sed -i '')
else
  SED_CMD=(sed -i)
fi

## Remove the department variable
f3="using_department: true"
r3=""

"${SED_CMD[@]}" "s/${f3}/${r3}/g" dbt_project.yml

## Remove all the references to using_department
SOLUTIONS_DIR="$(dirname "$(readlink -f "${BASH_SOURCE}")")/solutions"

## In intermediate directory
cp $SOLUTIONS_DIR/int_quickbooks__expenses_union.sql models/intermediate/int_quickbooks__expenses_union.sql
cp $SOLUTIONS_DIR/int_quickbooks__sales_union.sql models/intermediate/int_quickbooks__sales_union.sql


## Not in intermediate directory
cp $SOLUTIONS_DIR/quickbooks__ap_ar_enhanced.sql models/quickbooks__ap_ar_enhanced.sql

## Fix the data issue from quickbooks001
# Disable the package models in dbt_project.yml
yq -i '.models.quickbooks_source.stg_quickbooks__refund_receipt."+enabled" = false' dbt_project.yml
yq -i '.models.quickbooks_source.stg_quickbooks__sales_receipt."+enabled" = false' dbt_project.yml
yq -i '.models.quickbooks_source.stg_quickbooks__estimate."+enabled" = false' dbt_project.yml

# Create staging directory if it doesn't exist
mkdir -p models/staging

# Copy our override models that handle the epoch-to-date conversion
cp $SOLUTIONS_DIR/stg_quickbooks__refund_receipt.sql models/staging/
cp $SOLUTIONS_DIR/stg_quickbooks__sales_receipt.sql models/staging/
cp $SOLUTIONS_DIR/stg_quickbooks__estimate.sql models/staging/
