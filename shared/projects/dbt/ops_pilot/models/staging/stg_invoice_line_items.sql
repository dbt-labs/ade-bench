with src as (
    select * from {{ source('ops_pilot', 'raw_invoice_line_items') }}
)
select
    trim(line_id) as line_item_id,
    trim(inv_id_fk) as invoice_id,
    lower(trim(li_typ_cd)) as line_type,
    trim(li_desc_txt) as description,
    coalesce({{ integer_from_text('qty_txt') }}, 0) as quantity,
    coalesce({{ numeric_from_text('unit_px_usd_txt') }}, 0) as unit_price_usd,
    coalesce({{ numeric_from_text('li_amt_usd_txt') }}, 0) as line_amount_usd,
    lower(trim(product_family_guess)) as product_family,
    coalesce({{ bool_from_text('recurring_hint') }}, false) as is_recurring_hint,
    case
        when lower(trim(li_typ_cd)) = 'base_subscription' then true
        else coalesce({{ bool_from_text('recurring_hint') }}, false)
    end as is_recurring_line
from src
