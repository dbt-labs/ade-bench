with src as (
    select * from {{ source('helixops_saas', 'raw_payments') }}
)
select
    trim(pmt_id) as payment_id,
    trim(inv_id_fk) as invoice_id,
    cast(nullif(trim(pmt_dt_txt), '') as date) as payment_date,
    lower(trim(pmt_method_cd)) as payment_method,
    case
        when lower(trim(pmt_stat_cd)) in ('paid', 'succeeded', 'settled') then 'paid'
        when lower(trim(pmt_stat_cd)) in ('failed', 'declined', 'error') then 'failed'
        else 'pending'
    end as payment_status,
    coalesce({{ numeric_from_text('amt_usd_txt') }}, 0) as amount_usd,
    coalesce({{ numeric_from_text('processor_fee_usd_txt') }}, 0) as processor_fee_usd,
    trim(gateway_msg_txt) as gateway_message,
    case
        when lower(trim(pmt_stat_cd)) in ('paid', 'succeeded', 'settled') then true
        else false
    end as is_successful_payment
from src
