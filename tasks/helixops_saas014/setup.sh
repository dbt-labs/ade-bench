#!/bin/bash
# Remove api_calls from stg_workspace_usage_daily
sed -i '/    coalesce({{ integer_from_text.*api_call_ct_txt.*) }}, 0) as api_calls,/d' models/staging/stg_workspace_usage_daily.sql
# Remove api_calls from int_workspace_daily_metrics
sed -i '/    u\.api_calls,/d' models/intermediate/int_workspace_daily_metrics.sql
# Remove api_calls from int_account_daily_usage
sed -i '/    sum(api_calls) as api_calls,/d' models/intermediate/int_account_daily_usage.sql
# Remove total_api_calls_30d from int_account_engagement (in usage_rollup CTE)
sed -i '/        sum(api_calls) as total_api_calls_30d,/d' models/intermediate/int_account_engagement.sql
# Remove total_api_calls_30d from int_account_engagement (in main select)
sed -i '/    coalesce(g\.total_api_calls_30d, 0) as total_api_calls_30d,/d' models/intermediate/int_account_engagement.sql
# Remove api_calls from fct_daily_account_usage
sed -i '/    u\.api_calls,/d' models/marts/fct_daily_account_usage.sql
# Remove latest_daily_api_calls and total_api_calls_30d from mart_account_360
sed -i '/    lu\.api_calls as latest_daily_api_calls,/d' models/marts/mart_account_360.sql
sed -i '/    e\.total_api_calls_30d,/d' models/marts/mart_account_360.sql
# Remove total_api_calls_30d from mart_account_health
sed -i '/    e\.total_api_calls_30d,/d' models/marts/mart_account_health.sql
dbt run
