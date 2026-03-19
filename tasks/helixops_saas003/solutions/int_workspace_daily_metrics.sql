with usage as (
    select * from {{ ref('stg_workspace_usage_daily') }}
),
workspaces as (
    select * from {{ ref('stg_workspaces') }}
),
accounts as (
    select * from {{ ref('stg_accounts') }}
)
select
    u.usage_id,
    u.workspace_id,
    w.account_id,
    a.account_name,
    a.industry,
    a.segment,
    a.region,
    a.billing_country,
    w.workspace_name,
    w.environment_tier,
    w.workspace_status,
    w.is_primary,
    u.usage_date,
    u.usage_week,
    u.weekday_num,
    u.is_weekend,
    u.active_users,
    u.projects_run,
    u.api_calls,
    u.storage_gb,
    u.alerts_sent
from usage u
left join workspaces w using (workspace_id)
left join accounts a on w.account_id = a.account_id
where w.environment_tier != 'sandbox'
