{{
    config(
        materialized='incremental',
        unique_key='message_reaction_id',
        partition_by=['message_date'],
        incremental_strategy='merge'
    )
}}

-- get new data from staging
with dim_messages as (
    select * from {{ ref('dim_slack_messages') }}
    {% if is_incremental() %}
        where extracted_at > (
            select max(extracted_at) from {{ this }}
        )
    {% endif %}
)

,semi_expanded_reactions as (
    select
        message_id,
        channel_name,
        reaction.users as reaction_users,
        reaction.name as reaction_name,
        message_date,
        message_datetime,
        extracted_at
    from dim_messages
    {{ unnest_array('reactions', 'reaction') }}
)

,expanded_reactions as (
    select
        message_id,
        channel_name,
        reaction_name,
        reaction_user,
        message_date,
        message_datetime,
        extracted_at
    from semi_expanded_reactions
    {{ unnest_array('reaction_users', 'reaction_user') }}
)

,dimension as (
    select
        {{ dbt_utils.generate_surrogate_key(['message_id', 'reaction_user', 'reaction_name']) }} as message_reaction_id,
        message_id,
        message_date,
        message_datetime,
        channel_name,
        reaction_name,
        -- normalise reaction name to remove skin tone suffix
        case when instr(reaction_name, '::skin-tone') > 0 
            then split(reaction_name, '::')[0] 
            else reaction_name 
            end as reaction_name_normalised,
        reaction_user,
        extracted_at
    from expanded_reactions s
)

select * from dimension
