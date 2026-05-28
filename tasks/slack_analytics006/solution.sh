#!/bin/bash

mkdir -p models/marts

cat > models/marts/mart_channel_engagement.sql << 'DBTEOF'
with message_stats as (
    select
        channel_name,
        count(distinct message_id) as total_messages,
        sum(reply_count) as total_replies,
        sum(reply_users_count) as total_reply_users
    from {{ ref('dim_slack_messages') }}
    group by channel_name
)

,reaction_stats as (
    select
        channel_name,
        count(*) as total_reactions,
        count(distinct reaction_name_normalised) as distinct_reaction_types,
        count(distinct reaction_user) as distinct_reactors
    from {{ ref('fct_slack_message_reactions') }}
    group by channel_name
)

,reaction_rankings as (
    select
        channel_name,
        reaction_name_normalised,
        count(*) as reaction_count,
        row_number() over (
            partition by channel_name
            order by count(*) desc, reaction_name_normalised asc
        ) as rn
    from {{ ref('fct_slack_message_reactions') }}
    group by channel_name, reaction_name_normalised
)

,top_reactions as (
    select
        channel_name,
        reaction_name_normalised as most_common_reaction
    from reaction_rankings
    where rn = 1
)

select
    m.channel_name,
    m.total_messages,
    coalesce(r.total_reactions, 0) as total_reactions,
    coalesce(r.distinct_reaction_types, 0) as distinct_reaction_types,
    coalesce(r.distinct_reactors, 0) as distinct_reactors,
    round(coalesce(r.total_reactions, 0)::decimal / m.total_messages, 2) as avg_reactions_per_message,
    m.total_replies,
    m.total_reply_users,
    t.most_common_reaction
from message_stats m
left join reaction_stats r on m.channel_name = r.channel_name
left join top_reactions t on m.channel_name = t.channel_name
DBTEOF

cat > models/marts/_models.yml << 'YMLEOF'
version: 2
models:
  - name: mart_channel_engagement
    description: |
      Channel-level engagement summary combining message activity and reaction metrics.
      One row per channel.
    columns:
      - name: channel_name
        data_type: string
        description: The name of the Slack channel.
        tests:
          - unique
          - not_null
      - name: total_messages
        data_type: bigint
        description: Count of distinct messages in the channel.
      - name: total_reactions
        data_type: bigint
        description: Total number of reactions in the channel.
      - name: distinct_reaction_types
        data_type: bigint
        description: Count of distinct normalised reaction types used in the channel.
      - name: distinct_reactors
        data_type: bigint
        description: Count of distinct users who reacted in the channel.
      - name: avg_reactions_per_message
        data_type: decimal
        description: Average reactions per message, rounded to 2 decimal places.
      - name: total_replies
        data_type: bigint
        description: Sum of reply_count across all messages in the channel.
      - name: total_reply_users
        data_type: bigint
        description: Sum of reply_users_count across all messages in the channel.
      - name: most_common_reaction
        data_type: string
        description: The most frequently used normalised reaction name in the channel. NULL if no reactions.
YMLEOF

dbt deps
dbt run --select mart_channel_engagement
