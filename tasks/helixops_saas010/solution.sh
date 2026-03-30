#!/bin/bash
patch -p1 < /sage/solutions/changes.patch
dbt run --select stg_workspaces int_account_workspaces
