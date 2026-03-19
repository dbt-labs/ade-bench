#!/bin/bash
sed -i '/    u.department,/d' models/intermediate/int_workspace_roster.sql
dbt run --select int_workspace_roster
