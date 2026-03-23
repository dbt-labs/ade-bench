#!/bin/bash
patch -p1 < /sage/solutions/changes.patch
dbt run --select int_account_billing_snapshot mart_account_360 mart_account_health
