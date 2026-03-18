with src as (
    select * from {{ source('helixops_saas', 'raw_workspace_usage_daily') }}
)
select
    trim(usage_id) as usage_id,
    trim(ws_id_fk) as workspace_id,
    cast(nullif(trim(usage_dt_txt), '') as date) as usage_date,
    coalesce({{ integer_from_text('active_usr_cnt_txt') }}, 0) as active_users,
    coalesce({{ integer_from_text('proj_runs_txt') }}, 0) as projects_run,
    coalesce({{ integer_from_text('api_call_ct_txt') }}, 0) as api_calls,
    coalesce({{ numeric_from_text('storage_gb_txt') }}, 0) as storage_gb,
    coalesce({{ integer_from_text('alerts_sent_txt') }}, 0) as alerts_sent,
    coalesce({{ bool_from_text('is_weekend_guess') }}, false) as is_weekend,
    cast(date_trunc('week', cast(nullif(trim(usage_dt_txt), '') as date)) as date) as usage_week,
    extract('dow' from cast(nullif(trim(usage_dt_txt), '') as date)) as weekday_num
from src
