#!/bin/bash
set -euo pipefail
## Remove the using_department variable and disable package models,
## then copy replacement staging models
mkdir -p models/staging

yq -i '.models.quickbooks_source["stg_quickbooks__refund_receipt"]["+enabled"] = false' dbt_project.yml
yq -i '.models.quickbooks_source["stg_quickbooks__sales_receipt"]["+enabled"] = false' dbt_project.yml
yq -i '.models.quickbooks_source["stg_quickbooks__estimate"]["+enabled"] = false' dbt_project.yml
yq -i 'del(.vars.quickbooks.using_department)' dbt_project.yml

# Patch SQL model files and add override staging models
patch -p1 < /sage/solutions/changes.patch
