-- Define columns to compare
{% set table_name = 'int_quickbooks__sales_union' %}
{% set answer_keys = ['solution__int_quickbooks__sales_union'] %}

{% set cols_to_include = [
    
] %}

{% set cols_to_exclude = [
    
] %}


-------------------------------------
---- DO NOT EDIT BELOW THIS LINE ----
-- depends_on: {{ ref(table_name) }}
-- depends_on: {{ ref('solution__int_quickbooks__sales_union') }}

{{ ade_bench_equality_test(table_name=table_name, answer_keys=answer_keys, cols_to_exclude=cols_to_exclude) }}
