{% set table_name = 'stg_quickbooks__estimate' %}



-------------------------------------
---- DO NOT EDIT BELOW THIS LINE ----
{% set answer_key = 'solution__' + table_name %}

{% set table_a = adapter.get_relation(database=target.database, schema=target.schema, identifier=answer_key) %}
{% set table_b = adapter.get_relation(database=target.database, schema=target.schema, identifier=table_name) %}

{% if table_a is none or table_b is none %}
    select 1
{% else %}
    select 1 where false
{% endif %}
