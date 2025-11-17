{{
    config(
        materialized='incremental',
        unique_key='message_id',
        partition_by=['message_date'],
        incremental_strategy='merge'
    )
}}

-- get new data from staging
with staging as (

    select 
        message_id,
        user_id,
        channel_name,
        cast(reply_count as INT) as reply_count, 
        cast(reply_users_count as INT) as reply_users_count,
        reply_users,
        reactions,
        {{ to_date('message_datetime', localize=True, timezone=var('local_timezone')) }} as message_date,
        message_datetime,
        extracted_at
    from {{ ref('stg_channel_messages') }}
    {% if is_incremental() %}
        where extracted_at > (
            select max(extracted_at) from {{ this }}
        )
    {% endif %}        
)

-- row number comparison to be removed after first table build
-- get the latest row per message_id
,dimension as (
    select
        message_id,
        user_id,
        channel_name,
        reply_count,
        reply_users_count,
        reply_users,
        reactions,
        message_date,
        message_datetime,
        extracted_at

    from staging 
    where 1=1
    qualify row_number() over (partition by message_id order by extracted_at desc) = 1
)

select * from dimension