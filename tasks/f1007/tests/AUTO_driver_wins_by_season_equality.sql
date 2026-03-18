-- Define columns to compare
{% set table_name = 'driver_wins_by_season' %}
{% set answer_keys = ['solution__driver_wins_by_season'] %}

{% set cols_to_include = [
    
] %}

{% set cols_to_exclude = [
    
] %}


-------------------------------------
---- DO NOT EDIT BELOW THIS LINE ----
-- depends_on: {{ ref(table_name) }}
-- depends_on: {{ ref('solution__driver_wins_by_season') }}

{{ ade_bench_equality_test(table_name=table_name, answer_keys=answer_keys, cols_to_exclude=cols_to_exclude) }}
