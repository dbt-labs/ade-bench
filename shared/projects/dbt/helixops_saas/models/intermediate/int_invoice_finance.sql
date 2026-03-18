with invoices as (
    select * from {{ ref('stg_invoices') }}
),
line_items as (
    select * from {{ ref('stg_invoice_line_items') }}
),
payments as (
    select * from {{ ref('stg_payments') }}
),
line_rollup as (
    select
        invoice_id,
        count(*) as line_item_count,
        sum(case when is_recurring_line then line_amount_usd else 0 end) as recurring_revenue_usd,
        sum(case when not is_recurring_line then line_amount_usd else 0 end) as one_time_revenue_usd,
        sum(case when line_type = 'base_subscription' then line_amount_usd else 0 end) as base_subscription_revenue_usd
    from line_items
    group by 1
),
payment_rollup as (
    select
        invoice_id,
        count(*) as payment_attempt_count,
        sum(case when payment_status = 'paid' then 1 else 0 end) as successful_payment_count,
        sum(case when payment_status = 'failed' then 1 else 0 end) as failed_payment_count,
        sum(case when payment_status = 'paid' then amount_usd else 0 end) as amount_paid_usd,
        sum(case when payment_status = 'paid' then processor_fee_usd else 0 end) as processor_fee_usd
    from payments
    group by 1
),
latest_payment as (
    select *
    from (
        select
            p.*,
            row_number() over (partition by invoice_id order by payment_date desc, payment_id desc) as rn
        from payments p
    ) ranked
    where rn = 1
)
select
    i.invoice_id,
    i.subscription_id,
    i.account_id,
    i.invoice_date,
    i.invoice_month,
    i.due_date,
    i.service_period_start,
    i.service_period_end,
    i.invoice_status,
    i.subtotal_usd,
    i.tax_usd,
    i.total_usd,
    coalesce(l.line_item_count, 0) as line_item_count,
    coalesce(l.recurring_revenue_usd, 0) as recurring_revenue_usd,
    coalesce(l.one_time_revenue_usd, 0) as one_time_revenue_usd,
    coalesce(l.base_subscription_revenue_usd, 0) as base_subscription_revenue_usd,
    coalesce(p.payment_attempt_count, 0) as payment_attempt_count,
    coalesce(p.successful_payment_count, 0) as successful_payment_count,
    coalesce(p.failed_payment_count, 0) as failed_payment_count,
    coalesce(p.amount_paid_usd, 0) as amount_paid_usd,
    coalesce(p.processor_fee_usd, 0) as processor_fee_usd,
    lp.payment_status as latest_payment_status,
    lp.payment_method as latest_payment_method,
    lp.payment_date as latest_payment_date,
    greatest(i.total_usd - coalesce(p.amount_paid_usd, 0), 0) as outstanding_amount_usd,
    case when greatest(i.total_usd - coalesce(p.amount_paid_usd, 0), 0) <= 0.01 then true else false end as is_fully_paid
from invoices i
left join line_rollup l using (invoice_id)
left join payment_rollup p using (invoice_id)
left join latest_payment lp using (invoice_id)
