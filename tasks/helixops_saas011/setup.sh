#!/bin/bash
patch -p1 < /app/setup/changes.patch
dbt run --select stg_workspaces int_account_workspaces dim_accounts
