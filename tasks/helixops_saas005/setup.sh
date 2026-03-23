#!/bin/bash
patch -p1 < /app/setup/changes.patch
dbt run --select stg_users int_workspace_roster || true
