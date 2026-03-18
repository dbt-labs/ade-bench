with daily as (
    select * from {{ ref('int_workspace_daily_metrics') }}
)
select
    account_id,
    max(account_name) as account_name,
    max(industry) as industry,
    max(segment) as segment,
    max(region) as region,
    max(billing_country) as billing_country,
    usage_date,
    count(*) as workspace_days_reporting,
    sum(active_users) as active_users,
    sum(projects_run) as projects_run,
    sum(api_calls) as api_calls,
    sum(alerts_sent) as alerts_sent,
    max(storage_gb) as max_storage_gb,
    avg(storage_gb) as avg_storage_gb
from daily
group by 1,7
