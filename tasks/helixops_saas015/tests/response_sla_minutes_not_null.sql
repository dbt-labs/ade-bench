select 1 from {{ ref('fct_support_tickets') }} where response_sla_minutes is not null limit 0
