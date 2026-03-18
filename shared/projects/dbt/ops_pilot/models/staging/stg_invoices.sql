with src as (
    select * from {{ source('ops_pilot', 'raw_invoices') }}
)
select
    trim(inv_id) as invoice_id,
    trim(sub_id_fk) as subscription_id,
    trim(acct_id_fk) as account_id,
    cast(nullif(trim(inv_dt_txt), '') as date) as invoice_date,
    cast(nullif(trim(due_dt_txt), '') as date) as due_date,
    cast(nullif(trim(svc_prd_start_txt), '') as date) as service_period_start,
    cast(nullif(trim(svc_prd_end_txt), '') as date) as service_period_end,
    case
        when lower(trim(inv_stat_cd)) in ('paid', 'settled') then 'paid'
        when lower(trim(inv_stat_cd)) in ('past_due') then 'past_due'
        else 'open'
    end as invoice_status,
    coalesce({{ numeric_from_text('subtotal_usd_txt') }}, 0) as subtotal_usd,
    coalesce({{ numeric_from_text('tax_usd_txt') }}, 0) as tax_usd,
    coalesce({{ numeric_from_text('total_usd_txt') }}, 0) as total_usd,
    upper(trim(curr_cd)) as currency_code,
    cast(date_trunc('month', cast(nullif(trim(inv_dt_txt), '') as date)) as date) as invoice_month,
    case when lower(trim(inv_stat_cd)) in ('paid', 'settled') then true else false end as is_paid_invoice,
    case when lower(trim(inv_stat_cd)) in ('open', 'past_due') then true else false end as is_open_invoice
from src
