-- Define columns to compare
{% set table_name = 'quickbooks__ap_ar_enhanced' %}
{% set answer_keys = ['solution__quickbooks__ap_ar_enhanced'] %}

{% set cols_to_include = [
    
] %}

{% set cols_to_exclude = [
    'source_relation',
    'customer_vendor_address_line'
] %}


-------------------------------------
---- DO NOT EDIT BELOW THIS LINE ----
-- depends_on: {{ ref(table_name) }}
-- depends_on: {{ ref('solution__quickbooks__ap_ar_enhanced') }}

{{ ade_bench_equality_test(table_name=table_name, answer_keys=answer_keys, cols_to_exclude=cols_to_exclude) }}
