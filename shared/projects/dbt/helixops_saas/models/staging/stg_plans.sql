with src as (
    select * from {{ source('helixops_saas', 'raw_plans') }}
)
select
    trim(plan_sku) as plan_id,
    trim(plan_nm) as plan_name,
    case when lower(trim(bill_cadence_txt)) like 'annual%' then 'annual' else 'monthly' end as billing_cycle,
    {{ numeric_from_text('list_px_usd_txt') }} as list_price_usd,
    {{ integer_from_text('incl_seats_txt') }} as included_seats,
    {{ integer_from_text('ws_cap_txt') }} as max_workspaces,
    lower(trim(support_lvl_txt)) as support_tier,
    {{ integer_from_text('plan_rank_txt') }} as plan_rank,
    case
        when lower(trim(plan_nm)) like 'starter%' then 'starter'
        when lower(trim(plan_nm)) like 'growth%' then 'growth'
        else 'enterprise'
    end as plan_family,
    case when lower(trim(bill_cadence_txt)) like 'annual%' then true else false end as is_annual
from src
where coalesce({{ bool_from_text('deprecated_flag') }}, false) = false
