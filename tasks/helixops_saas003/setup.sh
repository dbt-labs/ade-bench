#!/bin/bash
# Replace the CASE for environment_tier with a raw passthrough (no normalization)
python3 -c "
import re
with open('models/staging/stg_workspaces.sql', 'r') as f:
    content = f.read()
old = '''    case
        when lower(trim(env_tier)) in ('sandbox', 'sbx') then 'sandbox'
        else 'prod'
    end as environment_tier,'''
new = '    lower(trim(env_tier)) as environment_tier,'
content = content.replace(old, new)
with open('models/staging/stg_workspaces.sql', 'w') as f:
    f.write(content)
"
# Remove environment_tier from int_workspace_daily_metrics
sed -i '/    w.environment_tier,/d' models/intermediate/int_workspace_daily_metrics.sql
dbt run --select stg_workspaces int_workspace_daily_metrics int_account_daily_usage
