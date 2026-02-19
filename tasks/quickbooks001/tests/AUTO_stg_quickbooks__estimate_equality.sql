-- Define columns to compare
{% set table_name = 'stg_quickbooks__estimate' %}

{% set cols_to_include = [
    
] %}

{% set cols_to_exclude = [
    'source_relation'
] %}



-------------------------------------
---- DO NOT EDIT BELOW THIS LINE ----
{% set answer_key = 'solution__' + table_name %}

-- depends_on: {{ ref(answer_key) }}
-- depends_on: {{ ref(table_name) }}

{% set table_a = adapter.get_relation(database=target.database, schema=target.schema, identifier=answer_key) %}
{% set table_b = adapter.get_relation(database=target.database, schema=target.schema, identifier=table_name) %}

{% if table_a is none or table_b is none %}
    select 1
{% else %}
    {{ dbt_utils.test_equality(
        model=ref(answer_key),
        compare_model=ref(table_name),
        compare_columns=cols_to_include,
        exclude_columns=cols_to_exclude
    ) }}
{% endif %}
