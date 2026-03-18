with src as (
    select * from {{ source('ops_pilot', 'raw_workspaces') }}
)
select
    trim(ws_id) as workspace_id,
    trim(acct_id_fk) as account_id,
    trim(ws_nm) as workspace_name,
    {{ epoch_to_timestamp('crt_ts_epoch') }} as created_at,
    case
        when lower(trim(ws_stat_cd)) in ('arch', 'archived', 'disabled') then 'archived'
        else 'active'
    end as workspace_status,
    {{ epoch_to_timestamp('deact_ts_epoch') }} as deactivated_at,
    case
        when lower(trim(env_tier)) in ('sandbox', 'sbx') then 'sandbox'
        else 'prod'
    end as environment_tier,
    coalesce({{ bool_from_text('primary_ws_yn') }}, false) as is_primary,
    case
        when lower(trim(ws_stat_cd)) in ('arch', 'archived', 'disabled') then false
        else true
    end as is_active_workspace,
    trim(load_epoch) as raw_load_epoch
from src
where coalesce({{ bool_from_text('soft_delete_ind') }}, false) = false
