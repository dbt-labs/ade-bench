#!/bin/bash
# Remove email from stg_users
sed -i '/    lower(trim(email_addr)) as email,/d' models/staging/stg_users.sql
# Rename u.email to u.email_address in int_account_users
sed -i 's/    u\.email,/    u.email_address,/' models/intermediate/int_account_users.sql
# Remove u.email from int_workspace_roster (remove the hint that email exists)
sed -i '/    u\.email,/d' models/intermediate/int_workspace_roster.sql
# Build what we can (int_account_users will fail - that's the broken state)
dbt run --select stg_users int_workspace_roster || true
