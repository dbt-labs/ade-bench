select 1 from {{ ref('mart_account_360') }} where net_mrr is not null limit 0
