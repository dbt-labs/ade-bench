with subs as (
    select * from {{ ref('stg_subscriptions') }}
),
plans as (
    select * from {{ ref('stg_plans') }}
),
accounts as (
    select * from {{ ref('stg_accounts') }}
)
select
    s.subscription_id,
    s.account_id,
    a.account_name,
    a.segment,
    a.region,
    s.plan_id,
    p.plan_name,
    p.plan_family,
    p.billing_cycle,
    p.support_tier,
    s.start_date,
    s.end_date,
    s.subscription_status,
    s.contracted_seats,
    s.auto_renew,
    s.discount_pct,
    p.list_price_usd,
    case
        when p.billing_cycle = 'annual' then round((p.list_price_usd * (1 - s.discount_pct / 100.0)) / 12.0, 2)
        else round(p.list_price_usd * (1 - s.discount_pct / 100.0), 2)
    end as effective_monthly_value_usd,
    cast(date_trunc('month', s.start_date) as date) as subscription_start_month,
    case when s.subscription_status = 'active' then true else false end as is_active_subscription
from subs s
left join plans p using (plan_id)
left join accounts a using (account_id)
