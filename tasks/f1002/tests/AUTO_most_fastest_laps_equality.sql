-- Define columns to compare
{% set table_name = 'most_fastest_laps' %}
{% set answer_keys = ['solution__most_fastest_laps'] %}

{% set cols_to_include = [
    
] %}

{% set cols_to_exclude = [
    'driver_full_name'
] %}


-------------------------------------
---- DO NOT EDIT BELOW THIS LINE ----
-- depends_on: {{ ref(table_name) }}
-- depends_on: {{ ref('solution__most_fastest_laps') }}

{{ ade_bench_equality_test(table_name=table_name, answer_keys=answer_keys, cols_to_exclude=cols_to_exclude) }}
