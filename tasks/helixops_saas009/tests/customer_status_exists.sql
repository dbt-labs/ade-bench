select 1 from {{ ref('dim_accounts_v2') }} where customer_status is not null limit 0
