#!/bin/bash

## Insert a second extraction of an existing message with a newer extracted_datetime
## and an updated reply_count, simulating a re-extraction from the Slack API.
if [[ "$*" == *"--db-type=duckdb"* ]]; then
    schema='main'
else
    schema='public'
fi

/scripts/run_sql.sh "$@" << SQL
insert into ${schema}.channel_messages_stats_with_reactions
    (id, message_id, user_id, reply_count, reply_users_count,
     message_datetime, extracted_datetime, reply_users, channel_name, reactions)
select
    id,
    message_id,
    user_id,
    reply_count + 5,
    reply_users_count + 2,
    message_datetime,
    extracted_datetime + interval '1 hour',
    reply_users,
    channel_name,
    reactions
from ${schema}.channel_messages_stats_with_reactions
where message_id = '82e710eb-abbc-450c-b8a9-e341d5b063a7';
SQL

## Break the deduplication ordering: change DESC to ASC so the model
## picks the oldest extraction instead of the latest.
cat > models/dimensions/dim_slack_messages.sql << 'DBTEOF'
{{
    config(
        materialized='incremental',
        unique_key='message_id',
        partition_by=['message_date'],
        incremental_strategy='delete+insert'
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
        extracted_datetime
    from {{ ref('stg_channel_messages') }}
    {% if is_incremental() %}
        where extracted_datetime > (
            select max(extracted_datetime) from {{ this }}
        )
    {% endif %}        
)

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
        extracted_datetime

    from staging 
    where 1=1
    qualify row_number() over (partition by message_id order by extracted_datetime asc) = 1
)

select * from dimension
DBTEOF

dbt deps
dbt run
