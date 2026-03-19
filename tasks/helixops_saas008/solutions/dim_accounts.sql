with accounts as (
    select * from {{ ref('stg_accounts') }}
),
workspace_rollup as (
    select * from {{ ref('int_account_workspaces') }}
),
user_rollup as (
    select
        account_id,
        count(*) as user_count,
        sum(case when user_status = 'active' then 1 else 0 end) as active_user_count,
        sum(case when user_status = 'inactive' then 1 else 0 end) as inactive_user_count,
        sum(case when user_status = 'provisioned' then 1 else 0 end) as provisioned_user_count
    from {{ ref('int_account_users') }}
    group by 1
)
select
    a.account_id,
    a.account_name,
    a.industry,
    a.region,
    a.segment,
    a.billing_country,
    a.created_at,
    a.customer_status,
    a.is_churned,
    a.employee_band,
    a.owner_team,
    coalesce(w.workspace_count, 0) as workspace_count,
    coalesce(w.active_workspace_count, 0) as active_workspace_count,
    coalesce(w.prod_workspace_count, 0) as prod_workspace_count,
    coalesce(w.sandbox_workspace_count, 0) as sandbox_workspace_count,
    w.primary_workspace_name,
    coalesce(u.user_count, 0) as user_count,
    coalesce(u.active_user_count, 0) as active_user_count,
    coalesce(u.inactive_user_count, 0) as inactive_user_count,
    coalesce(u.provisioned_user_count, 0) as provisioned_user_count
from accounts a
left join workspace_rollup w using (account_id)
left join user_rollup u using (account_id)
