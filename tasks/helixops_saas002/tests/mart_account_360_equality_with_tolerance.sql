{% set table_name = 'mart_account_360' %}
{% set answer_key = 'solution__mart_account_360' %}
{% set float_cols = ['discount_pct', 'avg_active_users_7d', 'avg_active_users_30d', 'peak_storage_gb_30d', 'avg_csat_score', 'avg_first_response_minutes'] %}
{% set precision = 6 %}

-- depends_on: {{ ref(table_name) }}
-- depends_on: {{ ref(answer_key) }}

{% if execute %}
    {% set seed_rel = load_relation(ref(answer_key)) %}
    {% if seed_rel is none %}
        select 1
    {% else %}
        {% set columns = adapter.get_columns_in_relation(seed_rel) %}
        {% set select_exprs = [] %}
        {% for col in columns %}
            {% if col.name | lower in float_cols %}
                {% do select_exprs.append('round(' ~ col.quoted ~ ',' ~ precision ~ ') as ' ~ col.quoted) %}
            {% else %}
                {% do select_exprs.append(col.quoted) %}
            {% endif %}
        {% endfor %}
        {% set cols_sql = select_exprs | join(', ') %}

        with a_minus_b as (
            select {{ cols_sql }} from {{ ref(answer_key) }}
            except
            select {{ cols_sql }} from {{ ref(table_name) }}
        ),
        b_minus_a as (
            select {{ cols_sql }} from {{ ref(table_name) }}
            except
            select {{ cols_sql }} from {{ ref(answer_key) }}
        )
        select * from a_minus_b
        union all
        select * from b_minus_a
    {% endif %}
{% else %}
    select 1 where 1=0
{% endif %}
