-- Define columns to compare
{% set table_name = 'dim_slack_messages' %}
{% set answer_keys = ['solution__dim_slack_messages'] %}

{% set cols_to_include = [
    
] %}

{% set cols_to_exclude = [
    'reply_users',
    'reactions'
] %}


-------------------------------------
---- DO NOT EDIT BELOW THIS LINE ----
-- depends_on: {{ ref(table_name) }}
-- depends_on: {{ ref('solution__dim_slack_messages') }}

{{ ade_bench_equality_test(table_name=table_name, answer_keys=answer_keys, cols_to_exclude=cols_to_exclude) }}
