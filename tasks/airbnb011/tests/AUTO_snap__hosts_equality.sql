-- Define columns to compare
{% set table_name = 'snap__hosts' %}
{% set answer_keys = ['solution__snap__hosts', 'solution__snap__hosts_aliased'] %}

{% set cols_to_include = [
    
] %}

{% set cols_to_exclude = [
    'dbt_scd_id'
] %}


-------------------------------------
---- DO NOT EDIT BELOW THIS LINE ----
-- depends_on: {{ ref(table_name) }}
-- depends_on: {{ ref('solution__snap__hosts') }}
-- depends_on: {{ ref('solution__snap__hosts_aliased') }}

{{ ade_bench_equality_test(table_name=table_name, answer_keys=answer_keys, cols_to_exclude=cols_to_exclude) }}
