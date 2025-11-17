with source as (

    select * from {{ source('slack_analytics', 'channel_messages') }}

),

renamed as (
    select
        message_id,
        user_id,
        channel_name,
        reply_count, 
        reply_users_count,
        {{ parse_json('reply_users') }} as reply_users,
        {{ parse_json('reactions') }} as reactions,
        message_datetime,
        extracted_at
    from source
)

select * from renamed