with users as (
    select * from {{ ref('stg_users') }}
),
accounts as (
    select * from {{ ref('stg_accounts') }}
)
select
    u.user_id,
    u.account_id,
    a.account_name,
    a.industry,
    a.region,
    a.segment,
    a.billing_country,
    a.account_status,
    a.owner_team,
    u.email,
    u.full_name,
    u.title,
    u.department,
    u.created_at,
    u.last_login_at,
    u.user_status,
    u.is_active_user,
    u.is_test_user,
    date_diff('day', cast(u.last_login_at as date), cast(now() as date)) as days_since_last_login
from users u
left join accounts a using (account_id)
