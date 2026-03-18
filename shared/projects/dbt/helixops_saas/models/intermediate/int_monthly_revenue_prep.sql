with finance as (
    select * from {{ ref('int_invoice_finance') }}
),
accounts as (
    select * from {{ ref('stg_accounts') }}
)
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
from finance f
left join accounts a using (account_id)
group by 1,2,3,4,5,6
