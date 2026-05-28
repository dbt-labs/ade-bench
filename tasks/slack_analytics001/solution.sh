#!/bin/bash
# Create the fact folder
mkdir -p models/facts

# Create the fct_slack_message_reactions table
cat > models/facts/fct_slack_message_reactions.sql << EOF
{{
    config(
        materialized='incremental',
        unique_key='message_reaction_id',
        partition_by=['message_date'],
        incremental_strategy='delete+insert'
    )
}}

-- get new data from staging
with dim_messages as (
    select * from {{ ref('dim_slack_messages') }}
    {% if is_incremental() %}
        where extracted_datetime > (
            select max(extracted_datetime) from {{ this }}
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
        extracted_datetime
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
        extracted_datetime
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
        extracted_datetime  
    from expanded_reactions s
)

select * from dimension

EOF

# Create the _models.yml file
cat > models/facts/_models.yml << EOF
version: 2
models:
  - name: fct_slack_message_reactions
    description: |
      This table expands reaction data for messages from dim_slack_messages. Contains one row per `message_reaction_id`.
    columns:
      - name: message_reaction_id
        data_type: string
        description: The surrogate key for the message reaction created using the message_id, reaction_name and reaction_user.
        tests:
          - unique
          - not_null
      - name: message_id
        data_type: string
        description: Unique identifier for the message. Foreign key to dim_slack_messages.
      - name: message_date
        data_type: date
        description: The date the message was sent.
      - name: message_datetime
        data_type: timestamp
        description: The date and time the message was sent.
      - name: channel_name
        data_type: string
        description: The name of the channel the message was sent in.
      - name: reaction_name
        data_type: string
        description: The name of the reaction used on the message.
      - name: reaction_name_normalised
        data_type: string
        description: The generic reaction name if the ``reaction_name`` contains skin-tone variations.
      - name: reaction_user
        data_type: string
        description: The user_id of the user who used the specified reaction to the message.
      - name: extracted_datetime
        data_type: timestamp
        description: The date and time the message was extracted from the Slack API.
EOF

dbt deps

# Run dbt to create the models
dbt run --select fct_slack_message_reactions
