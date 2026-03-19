with invoice_finance as (
    select * from {{ ref('int_invoice_finance') }}
),
stg_accounts as (
    select * from {{ ref('stg_accounts') }}
),
revenue as (
    select
        f.account_id,
        a.account_name,
        a.segment,
        a.region,
        a.billing_country,
        f.invoice_month,
        count(*) as invoice_count,
        sum(f.recurring_revenue_usd) as recurring_revenue_usd,
        sum(f.one_time_revenue_usd) as one_time_revenue_usd,
        sum(f.subtotal_usd) as subtotal_usd,
        sum(f.tax_usd) as tax_usd,
        sum(f.total_usd) as total_revenue_usd,
        sum(f.amount_paid_usd) as collected_revenue_usd,
        sum(f.outstanding_amount_usd) as outstanding_revenue_usd,
        sum(case when f.invoice_status = 'open' then 1 else 0 end) as open_invoice_count,
        sum(case when f.invoice_status = 'past_due' then 1 else 0 end) as past_due_invoice_count,
        sum(case when f.is_fully_paid then 1 else 0 end) as fully_paid_invoice_count
    from invoice_finance f
    left join stg_accounts a using (account_id)
    group by 1,2,3,4,5,6
),
billing as (
    select account_id, plan_name, latest_subscription_status, has_past_due_invoice from {{ ref('int_account_billing_snapshot') }}
)
select
    r.account_id,
    r.account_name,
    r.segment,
    r.region,
    r.billing_country,
    r.invoice_month,
    b.plan_name,
    b.latest_subscription_status,
    r.invoice_count,
    r.recurring_revenue_usd,
    r.one_time_revenue_usd,
    r.subtotal_usd,
    r.tax_usd,
    r.total_revenue_usd,
    r.collected_revenue_usd,
    r.outstanding_revenue_usd,
    r.open_invoice_count,
    r.past_due_invoice_count,
    b.has_past_due_invoice
from revenue r
left join billing b using (account_id)
