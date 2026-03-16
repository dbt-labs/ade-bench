-- Define columns to compare
{% set table_name = 'int_quickbooks__invoice_join' %}
{% set answer_keys = ['solution__int_quickbooks__invoice_join'] %}

{% set cols_to_include = [
    
] %}

{% set cols_to_exclude = [
    'source_relation'
] %}


-------------------------------------
---- DO NOT EDIT BELOW THIS LINE ----
-- depends_on: {{ ref(table_name) }}
-- depends_on: {{ ref('solution__int_quickbooks__invoice_join') }}

{% if not execute %}
    select 1 where 1=0
{% else %}
    {% set ns = namespace(matched=false) %}
    {% set actual_rel = load_relation(ref(table_name)) %}

    {% if actual_rel is not none %}
        {% set actual_columns = adapter.get_columns_in_relation(actual_rel) %}
        {% set exclude_lower = cols_to_exclude | map('lower') | list %}

        {%- set actual_col_names = [] -%}
        {%- for col in actual_columns -%}
            {%- if col.name | lower not in exclude_lower -%}
                {%- do actual_col_names.append(col.name | lower) -%}
            {%- endif -%}
        {%- endfor -%}
        {% set actual_set = actual_col_names | sort %}

        {% for answer_key in answer_keys %}
            {% if not ns.matched %}
                {% set seed_rel = load_relation(ref(answer_key)) %}
                {% if seed_rel is not none %}
                    {% set seed_columns = adapter.get_columns_in_relation(seed_rel) %}

                    {%- set seed_col_names = [] -%}
                    {%- for col in seed_columns -%}
                        {%- if col.name | lower not in exclude_lower -%}
                            {%- do seed_col_names.append(col.name | lower) -%}
                        {%- endif -%}
                    {%- endfor -%}
                    {% set seed_set = seed_col_names | sort %}

                    {% if actual_set == seed_set %}
                        {%- set compare_cols = [] -%}
                        {%- for col in actual_columns -%}
                            {%- if col.name | lower not in exclude_lower -%}
                                {%- do compare_cols.append(col.quoted) -%}
                            {%- endif -%}
                        {%- endfor -%}
                        {% set compare_cols_csv = compare_cols | join(', ') %}

                        {% set query %}
                            with a_minus_b as (
                                select {{ compare_cols_csv }} from {{ ref(answer_key) }}
                                except
                                select {{ compare_cols_csv }} from {{ ref(table_name) }}
                            ),
                            b_minus_a as (
                                select {{ compare_cols_csv }} from {{ ref(table_name) }}
                                except
                                select {{ compare_cols_csv }} from {{ ref(answer_key) }}
                            ),
                            unioned as (
                                select * from a_minus_b
                                union all
                                select * from b_minus_a
                            )
                            select count(*) as diff_count from unioned
                        {% endset %}

                        {% set result = run_query(query) %}
                        {% if result.rows[0][0] == 0 %}
                            {% set ns.matched = true %}
                        {% endif %}
                    {% endif %}
                {% endif %}
            {% endif %}
        {% endfor %}
    {% endif %}

    {% if ns.matched %}
        select 1 where 1=0
    {% else %}
        select 1
    {% endif %}
{% endif %}
