select 1 from {{ ref('mart_account_360') }} where geo_segment is not null limit 0
