with tickets as (
    select * from {{ ref('stg_support_tickets') }}
),
accounts as (
    select * from {{ ref('stg_accounts') }}
),
workspaces as (
    select * from {{ ref('stg_workspaces') }}
),
sla_targets as (
    select * from {{ ref('sla_response_targets') }}
)
select
    t.ticket_id,
    t.account_id,
    a.account_name,
    a.segment,
    a.region,
    a.billing_country,
    t.workspace_id,
    w.workspace_name,
    w.environment_tier,
    t.opened_by_user_id,
    t.opened_at,
    t.first_response_at,
    t.resolved_at,
    t.priority,
    t.category,
    t.ticket_status,
    t.csat_score,
    t.first_response_minutes,
    t.resolution_minutes,
    s.response_sla_minutes,
    s.response_sla_minutes >= t.first_response_minutes as met_response_sla,
    t.is_open_ticket,
    case
        when t.resolved_at is not null then date_diff('day', cast(t.opened_at as date), cast(t.resolved_at as date))
        else date_diff('day', cast(t.opened_at as date), cast(now() as date))
    end as ticket_age_days,
    cast(date_trunc('month', cast(t.opened_at as date)) as date) as opened_month,
    cast(date_trunc('month', cast(t.resolved_at as date)) as date) as resolved_month
from tickets t
left join accounts a using (account_id)
left join workspaces w on t.workspace_id = w.workspace_id
left join sla_targets s
    on t.priority = s.priority
    and t.opened_at >= cast(s.valid_from as timestamp)
    and t.opened_at < cast(s.valid_to as timestamp)
