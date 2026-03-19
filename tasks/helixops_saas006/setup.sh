#!/bin/bash
# Add list_price_usd to int_account_billing_snapshot (tempting trap input)
sed -i 's/    ls\.effective_monthly_value_usd,/    ls.effective_monthly_value_usd,\n    ls.list_price_usd,/' models/intermediate/int_account_billing_snapshot.sql
dbt run
