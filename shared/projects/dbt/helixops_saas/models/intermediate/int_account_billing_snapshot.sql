with sub_hist as (
    select * from {{ ref('int_subscription_history') }}
),
invoice_finance as (
    select * from {{ ref('int_invoice_finance') }}
),
sub_ranked as (
    select
        s.*,
        row_number() over (
            partition by account_id
            order by case when subscription_status = 'active' then 0 else 1 end, start_date desc, subscription_id desc
        ) as rn
    from sub_hist s
),
latest_sub as (
    select * from sub_ranked where rn = 1
),
inv_ranked as (
    select
        f.*,
        row_number() over (partition by account_id order by invoice_date desc, invoice_id desc) as rn
    from invoice_finance f
),
latest_inv as (
    select * from inv_ranked where rn = 1
),
acct_rollup as (
    select
        account_id,
        sum(case when invoice_status = 'past_due' then 1 else 0 end) as past_due_invoice_count,
        sum(case when invoice_status in ('open', 'past_due') then 1 else 0 end) as open_invoice_count,
        max(case when invoice_status = 'past_due' then 1 else 0 end) as has_past_due_invoice
    from invoice_finance
    group by 1
)
select
    coalesce(ls.account_id, li.account_id, ar.account_id) as account_id,
    ls.subscription_id as latest_subscription_id,
    ls.plan_id,
    ls.plan_name,
    ls.plan_family,
    ls.billing_cycle,
    ls.support_tier,
    ls.subscription_status as latest_subscription_status,
    ls.start_date as latest_subscription_start_date,
    ls.end_date as latest_subscription_end_date,
    ls.contracted_seats,
    ls.discount_pct,
    ls.effective_monthly_value_usd,
    li.invoice_id as latest_invoice_id,
    li.invoice_date as latest_invoice_date,
    li.due_date as latest_invoice_due_date,
    li.invoice_status as latest_invoice_status,
    li.latest_payment_status,
    li.latest_payment_method,
    li.latest_payment_date,
    li.total_usd as latest_invoice_total_usd,
    li.amount_paid_usd as latest_invoice_amount_paid_usd,
    li.outstanding_amount_usd as latest_outstanding_amount_usd,
    coalesce(ar.past_due_invoice_count, 0) as past_due_invoice_count,
    coalesce(ar.open_invoice_count, 0) as open_invoice_count,
    case when coalesce(ar.has_past_due_invoice, 0) = 1 then true else false end as has_past_due_invoice
from latest_sub ls
full outer join latest_inv li on ls.account_id = li.account_id
left join acct_rollup ar on coalesce(ls.account_id, li.account_id) = ar.account_id
