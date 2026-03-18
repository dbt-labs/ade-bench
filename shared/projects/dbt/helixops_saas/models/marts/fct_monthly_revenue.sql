with revenue as (
    select * from {{ ref('int_monthly_revenue_prep') }}
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
