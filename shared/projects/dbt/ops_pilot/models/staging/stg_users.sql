with src as (
    select * from {{ source('ops_pilot', 'raw_users') }}
)
select
    trim(usr_id) as user_id,
    trim(acct_id_fk) as account_id,
    lower(trim(email_addr)) as email,
    trim(full_nm) as full_name,
    trim(title_txt) as title,
    lower(trim(dept_txt)) as department,
    {{ epoch_to_timestamp('created_unix') }} as created_at,
    {{ epoch_to_timestamp('last_seen_unix') }} as last_login_at,
    case
        when lower(trim(user_stat_cd)) in ('active', 'enabled', 'actv') then 'active'
        when lower(trim(user_stat_cd)) in ('disabled', 'inactive', 'termd') then 'inactive'
        else 'provisioned'
    end as user_status,
    coalesce({{ bool_from_text('test_user_ind') }}, false) as is_test_user,
    case
        when lower(trim(user_stat_cd)) in ('active', 'enabled', 'actv') then true
        else false
    end as is_active_user,
    trim(legacy_user_num) as legacy_user_num
from src
