with src as (
    select * from {{ source('helixops_saas', 'raw_accounts') }}
)
select
    trim(acct_id) as account_id,
    trim(acct_nm) as account_name,
    lower(trim(indstry_cd)) as industry,
    upper(trim(geo_region)) as region,
    case lower(trim(segment_lbl))
        when 'enterprise' then 'enterprise'
        when 'mid-market' then 'mid_market'
        else 'smb'
    end as segment,
    upper(trim(bill_ctry)) as billing_country,
    {{ epoch_to_timestamp('created_ts_epoch') }} as created_at,
    case
        when lower(trim(acct_stat)) in ('cust_active', 'active', '1', 'current') then 'active'
        when lower(trim(acct_stat)) in ('churned', 'closed_lost', 'cancelled', 'closed') then 'churned'
        else 'active'
    end as account_status,
    trim(employee_band_txt) as employee_band,
    trim(owner_team_txt) as owner_team,
    {{ bool_from_text('is_deleted_flag') }} as is_deleted,
    trim(src_batch_id) as source_batch_id,
    case
        when lower(trim(acct_stat)) in ('churned', 'closed_lost', 'cancelled', 'closed') then true
        else false
    end as is_churned
from src
where coalesce({{ bool_from_text('is_deleted_flag') }}, false) = false
