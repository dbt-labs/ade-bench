with usage as (
    select * from {{ ref('int_account_daily_usage') }}
),
accounts as (
    select account_id, account_name, segment, region, industry from {{ ref('dim_accounts') }}
)
select
    u.account_id,
    a.account_name,
    a.segment,
    a.region,
    a.industry,
    u.usage_date,
    u.workspace_days_reporting,
    u.active_users,
    u.projects_run,
    u.api_calls,
    u.alerts_sent,
    u.max_storage_gb,
    u.avg_storage_gb
from usage u
left join accounts a using (account_id)
