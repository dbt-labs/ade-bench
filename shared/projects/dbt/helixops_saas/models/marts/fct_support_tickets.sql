with sla as (
    select * from {{ ref('int_support_sla') }}
),
billing as (
    select account_id, plan_name, plan_family, support_tier from {{ ref('int_account_billing_snapshot') }}
)
select
    s.ticket_id,
    s.account_id,
    s.account_name,
    s.segment,
    s.region,
    s.billing_country,
    b.plan_name,
    b.plan_family,
    b.support_tier,
    s.workspace_id,
    s.workspace_name,
    s.environment_tier,
    s.opened_by_user_id,
    s.opened_at,
    s.first_response_at,
    s.resolved_at,
    s.priority,
    s.category,
    s.ticket_status,
    s.csat_score,
    s.first_response_minutes,
    s.resolution_minutes,
    s.response_sla_minutes,
    s.met_response_sla,
    s.is_open_ticket,
    s.ticket_age_days,
    s.opened_month,
    s.resolved_month
from sla s
left join billing b using (account_id)
