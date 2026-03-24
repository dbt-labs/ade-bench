-- Define columns to compare
{% set table_name = 'stg_workspace_usage_daily' %}
{% set answer_keys = ['solution__stg_workspace_usage_daily'] %}

{% set cols_to_include = [
    
] %}

{% set cols_to_exclude = [
    
] %}


-------------------------------------
---- DO NOT EDIT BELOW THIS LINE ----
-- depends_on: {{ ref(table_name) }}
-- depends_on: {{ ref('solution__stg_workspace_usage_daily') }}

{{ ade_bench_equality_test(table_name=table_name, answer_keys=answer_keys, cols_to_exclude=cols_to_exclude) }}
