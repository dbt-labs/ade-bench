with memberships as (
    select * from {{ ref('stg_workspace_memberships') }}
),
users as (
    select * from {{ ref('stg_users') }}
),
workspaces as (
    select * from {{ ref('stg_workspaces') }}
),
accounts as (
    select * from {{ ref('stg_accounts') }}
)
select
    m.membership_id,
    m.workspace_id,
    w.workspace_name,
    w.environment_tier,
    w.workspace_status,
    w.is_primary,
    w.account_id,
    a.account_name,
    a.segment,
    a.region,
    a.billing_country,
    m.user_id,
    u.email,
    u.full_name,
    u.title,
    u.department,
    u.user_status,
    u.is_active_user,
    m.role,
    m.invited_at,
    m.joined_at,
    m.membership_status,
    m.is_current_membership
from memberships m
left join users u on m.user_id = u.user_id
left join workspaces w on m.workspace_id = w.workspace_id
left join accounts a on w.account_id = a.account_id
