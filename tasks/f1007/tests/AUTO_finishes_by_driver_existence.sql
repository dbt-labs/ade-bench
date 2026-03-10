{% set table_name = 'finishes_by_driver' %}



-------------------------------------
---- DO NOT EDIT BELOW THIS LINE ----
{% set answer_key = 'solution__' + table_name %}

{% set table_a = load_relation(ref(answer_key)) %}
{% set table_b = load_relation(ref(table_name)) %}

{% if table_a is none or table_b is none %}
    select 1
{% else %}
    select 1 where false
{% endif %}
