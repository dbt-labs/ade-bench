-- Define columns to compare
{% set table_name = 'analysis__lap_times' %}
{% set answer_keys = ['solution__analysis__lap_times', 'solution__analysis__lap_times_exclude_pit_stops'] %}

{% set cols_to_include = [
    
] %}

{% set cols_to_exclude = [
    
] %}


-------------------------------------
---- DO NOT EDIT BELOW THIS LINE ----
-- depends_on: {{ ref(table_name) }}
-- depends_on: {{ ref('solution__analysis__lap_times') }}
-- depends_on: {{ ref('solution__analysis__lap_times_exclude_pit_stops') }}

{{ ade_bench_equality_test(table_name=table_name, answer_keys=answer_keys, cols_to_exclude=cols_to_exclude) }}
