#!/bin/bash
patch -p1 < /sage/solutions/changes.patch
dbt run --select dim_accounts mart_account_360
