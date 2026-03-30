select 1 from {{ ref('dim_accounts', v=2) }} where customer_status is not null limit 0
