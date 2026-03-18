with src as (
    select * from {{ source('helixops_saas', 'raw_workspace_memberships') }}
)
select
    trim(mship_id) as membership_id,
    trim(ws_id_fk) as workspace_id,
    trim(usr_id_fk) as user_id,
    lower(trim(role_cd_dup)) as role,
    {{ epoch_to_timestamp('invited_unix') }} as invited_at,
    {{ epoch_to_timestamp('joined_unix') }} as joined_at,
    case
        when lower(trim(mship_stat_cd)) in ('removed', 'deleted') then 'removed'
        when lower(trim(mship_stat_cd)) in ('pending', 'invited') then 'pending'
        else 'active'
    end as membership_status,
    case
        when lower(trim(mship_stat_cd)) in ('a', 'active', 'current') then true
        else false
    end as is_current_membership
from src
