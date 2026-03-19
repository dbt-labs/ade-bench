#!/bin/bash
sed -i '/    a.billing_country,/d' models/marts/dim_accounts.sql
dbt run --select dim_accounts
