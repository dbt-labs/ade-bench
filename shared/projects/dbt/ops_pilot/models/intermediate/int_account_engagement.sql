with users as (
    select * from {{ ref('int_account_users') }}
),
workspaces as (
    select * from {{ ref('int_account_workspaces') }}
),
daily_usage as (
    select * from {{ ref('int_account_daily_usage') }}
),
user_rollup as (
    select
        account_id,
        count(*) as total_user_count,
        sum(case when user_status = 'active' then 1 else 0 end) as active_user_count,
        sum(case when user_status = 'inactive' then 1 else 0 end) as inactive_user_count,
        sum(case when user_status = 'provisioned' then 1 else 0 end) as provisioned_user_count,
        max(last_login_at) as latest_user_login_at
    from users
    group by 1
),
usage_rollup as (
    select
        account_id,
        max(usage_date) as latest_usage_date,
        avg(case when usage_date >= cast(now() as date) - interval 6 day then active_users end) as avg_active_users_7d,
        avg(active_users) as avg_active_users_30d,
        sum(projects_run) as total_projects_run_30d,
        sum(api_calls) as total_api_calls_30d,
        sum(alerts_sent) as total_alerts_30d,
        max(max_storage_gb) as peak_storage_gb_30d
    from daily_usage
    group by 1
)
select
    coalesce(u.account_id, w.account_id, g.account_id) as account_id,
    coalesce(u.total_user_count, 0) as total_user_count,
    coalesce(u.active_user_count, 0) as active_user_count,
    coalesce(u.inactive_user_count, 0) as inactive_user_count,
    coalesce(u.provisioned_user_count, 0) as provisioned_user_count,
    u.latest_user_login_at,
    coalesce(w.workspace_count, 0) as workspace_count,
    coalesce(w.active_workspace_count, 0) as active_workspace_count,
    coalesce(w.sandbox_workspace_count, 0) as sandbox_workspace_count,
    g.latest_usage_date,
    coalesce(g.avg_active_users_7d, 0) as avg_active_users_7d,
    coalesce(g.avg_active_users_30d, 0) as avg_active_users_30d,
    coalesce(g.total_projects_run_30d, 0) as total_projects_run_30d,
    coalesce(g.total_api_calls_30d, 0) as total_api_calls_30d,
    coalesce(g.total_alerts_30d, 0) as total_alerts_30d,
    coalesce(g.peak_storage_gb_30d, 0) as peak_storage_gb_30d
from user_rollup u
full outer join workspaces w on u.account_id = w.account_id
full outer join usage_rollup g on coalesce(u.account_id, w.account_id) = g.account_id
