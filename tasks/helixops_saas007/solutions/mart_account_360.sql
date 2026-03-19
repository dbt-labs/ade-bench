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
        count(*) as lifetime_ticket_count,
        sum(case when is_open_ticket then 1 else 0 end) as open_ticket_count,
        avg(csat_score) as avg_csat_score,
        avg(first_response_minutes) as avg_first_response_minutes
    from {{ ref('fct_support_tickets') }}
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
),
latest_usage as (
    select *
    from (
        select
            u.*,
            row_number() over (partition by account_id order by usage_date desc) as rn
        from {{ ref('fct_daily_account_usage') }} u
    ) ranked
    where rn = 1
)
select
    a.account_id,
    a.account_name,
    a.industry,
    a.region,
    a.segment,
    a.billing_country,
    a.account_status,
    a.is_churned,
    a.employee_band,
    a.owner_team,
    a.workspace_count,
    a.active_workspace_count,
    a.sandbox_workspace_count,
    a.primary_workspace_name,
    a.user_count,
    a.active_user_count,
    b.plan_name,
    b.plan_family,
    b.billing_cycle,
    b.support_tier,
    b.contracted_seats,
    b.discount_pct,
    b.latest_invoice_status,
    b.latest_payment_status,
    b.latest_invoice_date,
    b.latest_payment_date,
    b.latest_outstanding_amount_usd,
    b.has_past_due_invoice,
    b.geo_segment,
    lr.invoice_month as latest_revenue_month,
    lr.recurring_revenue_usd as latest_recurring_revenue_usd,
    lr.one_time_revenue_usd as latest_one_time_revenue_usd,
    lr.total_revenue_usd as latest_total_revenue_usd,
    lr.collected_revenue_usd as latest_collected_revenue_usd,
    lu.usage_date as latest_usage_date,
    lu.active_users as latest_daily_active_users,
    lu.projects_run as latest_daily_projects_run,
    lu.api_calls as latest_daily_api_calls,
    e.avg_active_users_7d,
    e.avg_active_users_30d,
    e.total_projects_run_30d,
    e.total_api_calls_30d,
    e.peak_storage_gb_30d,
    s.lifetime_ticket_count,
    s.open_ticket_count,
    s.avg_csat_score,
    s.avg_first_response_minutes
from accounts a
left join billing b using (account_id)
left join latest_revenue lr using (account_id)
left join latest_usage lu using (account_id)
left join engagement e using (account_id)
left join support_rollup s using (account_id)
