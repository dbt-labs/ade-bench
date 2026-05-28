#!/bin/bash
rm macros/unnest_array.sql

dbt deps
dbt run --select stg_channel_messages dim_slack_messages
