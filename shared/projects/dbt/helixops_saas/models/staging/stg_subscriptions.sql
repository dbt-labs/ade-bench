with src as (
    select * from {{ source('helixops_saas', 'raw_subscriptions') }}
)
select
    trim(sub_id) as subscription_id,
    trim(acct_id_fk) as account_id,
    trim(plan_sku_fk) as plan_id,
    cast(nullif(trim(sub_start_dt_txt), '') as date) as start_date,
    cast(nullif(trim(sub_end_dt_txt), '') as date) as end_date,
    case
        when lower(trim(sub_stat_cd)) in ('active', 'current') then 'active'
        when lower(trim(sub_stat_cd)) in ('upgraded') then 'upgraded'
        else 'canceled'
    end as subscription_status,
    {{ integer_from_text('seats_committed_txt') }} as contracted_seats,
    coalesce({{ bool_from_text('auto_rnw_ind') }}, false) as auto_renew,
    coalesce({{ numeric_from_text('disc_pct_txt') }}, 0) as discount_pct,
    nullif(trim(cancel_reason_txt), '') as cancel_reason,
    case when lower(trim(sub_stat_cd)) in ('active', 'current') then true else false end as is_current_subscription
from src
