with accounts as (
    select * from {{ ref('dim_accounts') }}
),
billing as (
    select * from {{ ref('int_account_billing_snapshot') }}
),
engagement as (
    select * from {{ ref('int_account_engagement') }}
),
support_rollup as (
    select
        account_id,
        sum(case when is_open_ticket then 1 else 0 end) as open_ticket_count,
        sum(case when not met_response_sla then 1 else 0 end) as breached_sla_ticket_count,
        avg(csat_score) as avg_csat_score,
        avg(first_response_minutes) as avg_first_response_minutes
    from {{ ref('int_support_sla') }}
    group by 1
),
latest_revenue as (
    select *
    from (
        select
            r.*,
            row_number() over (partition by account_id order by invoice_month desc) as rn
        from {{ ref('fct_monthly_revenue') }} r
    ) ranked
    where rn = 1
)
select
    a.account_id,
    a.account_name,
    a.segment,
    a.region,
    a.billing_country,
    a.customer_status,
    b.plan_name,
    b.latest_subscription_status,
    b.latest_invoice_status,
    b.latest_payment_status,
    b.latest_outstanding_amount_usd,
    b.has_past_due_invoice,
    e.active_user_count,
    e.active_workspace_count,
    e.avg_active_users_7d,
    e.total_projects_run_30d,
    e.total_api_calls_30d,
    s.open_ticket_count,
    s.breached_sla_ticket_count,
    s.avg_csat_score,
    lr.recurring_revenue_usd as latest_month_recurring_revenue_usd,
    lr.total_revenue_usd as latest_month_total_revenue_usd,
    (
        100
        - (case when b.has_past_due_invoice then 25 else 0 end)
        - (case when coalesce(s.open_ticket_count, 0) >= 3 then 15 when coalesce(s.open_ticket_count, 0) > 0 then 5 else 0 end)
        - (case when coalesce(e.avg_active_users_7d, 0) = 0 then 20 when coalesce(e.avg_active_users_7d, 0) < 3 then 10 else 0 end)
        - (case when a.customer_status = 'churned' then 40 else 0 end)
    ) as account_health_score
from accounts a
left join billing b using (account_id)
left join engagement e using (account_id)
left join support_rollup s using (account_id)
left join latest_revenue lr using (account_id)
