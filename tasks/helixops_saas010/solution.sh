#!/bin/bash
patch -p1 < /sage/solutions/changes.patch
dbt run --select int_account_workspaces
