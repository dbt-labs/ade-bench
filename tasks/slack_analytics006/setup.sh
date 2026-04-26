#!/bin/bash

# Build the existing project so dim_slack_messages and fct_slack_message_reactions
# are available for the agent to query and build on top of.
dbt deps
dbt run
