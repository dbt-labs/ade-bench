with src as (
    select * from {{ source('ops_pilot', 'raw_support_tickets') }}
)
select
    trim(tkt_id) as ticket_id,
    trim(acct_id_fk) as account_id,
    nullif(trim(ws_id_fk), '') as workspace_id,
    trim(opened_by_usr_id) as opened_by_user_id,
    {{ epoch_to_timestamp('opened_ts_epoch') }} as opened_at,
    {{ epoch_to_timestamp('first_rsp_ts_epoch') }} as first_response_at,
    {{ epoch_to_timestamp('resolved_ts_epoch') }} as resolved_at,
    case
        when lower(trim(prio_cd)) in ('urgent', 'sev1') then 'urgent'
        when lower(trim(prio_cd)) in ('high', 'sev2') then 'high'
        when lower(trim(prio_cd)) in ('med', 'medium') then 'medium'
        else 'low'
    end as priority,
    lower(trim(cat_cd)) as category,
    case
        when lower(trim(tkt_stat_cd)) in ('resolved', 'closed', 'done') then 'resolved'
        when lower(trim(tkt_stat_cd)) in ('working', 'pending', 'in_progress') then 'in_progress'
        else 'open'
    end as ticket_status,
    {{ integer_from_text('csat_txt') }} as csat_score,
    date_diff('minute', {{ epoch_to_timestamp('opened_ts_epoch') }}, {{ epoch_to_timestamp('first_rsp_ts_epoch') }}) as first_response_minutes,
    case
        when {{ epoch_to_timestamp('resolved_ts_epoch') }} is not null then date_diff('minute', {{ epoch_to_timestamp('opened_ts_epoch') }}, {{ epoch_to_timestamp('resolved_ts_epoch') }})
        else null
    end as resolution_minutes,
    case when {{ epoch_to_timestamp('resolved_ts_epoch') }} is null then true else false end as is_open_ticket
from src
