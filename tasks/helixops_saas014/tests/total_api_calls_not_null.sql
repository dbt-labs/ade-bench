select 1 from {{ ref('mart_account_360') }} where total_api_calls_30d is not null limit 0
