#!/bin/bash
python3 -c "
with open('models/staging/stg_workspaces.sql', 'r') as f:
    content = f.read()
old = \"\"\"    case
        when lower(trim(env_tier)) in ('sandbox', 'sbx') then 'sandbox'
        else 'prod'
    end as environment_tier,\"\"\"
new = '    lower(trim(env_tier)) as environment_tier,'
content = content.replace(old, new)
with open('models/staging/stg_workspaces.sql', 'w') as f:
    f.write(content)
"
dbt run --select stg_workspaces int_account_workspaces dim_accounts
