#!/bin/bash
patch -p1 < /app/setup/changes.patch
dbt run --select dim_accounts mart_account_360
