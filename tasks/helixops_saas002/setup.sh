#!/bin/bash
sed -i '/    a.owner_team,/d' models/marts/dim_accounts.sql
sed -i '/    a.owner_team,/d' models/marts/mart_account_360.sql
dbt run --select dim_accounts mart_account_360
