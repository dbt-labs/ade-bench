-- Define columns to compare
{% set table_name = 'snap__hosts' %}
{% set answer_key_1 = 'solution__snap__hosts' %}
{% set answer_key_2 = 'solution__solution__snap__hosts_alt_1' %}


{% set cols_to_include = [
    
] %}

{% set cols_to_exclude = [
    'dbt_scd_id'
] %}


-------------------------------------
---- DO NOT EDIT BELOW THIS LINE ----
-- depends_on: {{ ref(table_name) }}
-- depends_on: {{ ref(answer_key_1) }}
-- depends_on: {{ ref(answer_key_2) }}


{% set submitted_table = adapter.get_relation(database=target.database, schema=target.schema, identifier=table_name) %}
{% set answer_key_1_table = adapter.get_relation(database=target.database, schema=target.schema, identifier=answer_key_1) %}
{% set answer_key_2_table = adapter.get_relation(database=target.database, schema=target.schema, identifier=answer_key_2) %}


with

answer_key_1_test as (
    {% if submitted_table is none or answer_key_1_table is none %}
        select 1
    {% else %}
        {{ dbt_utils.test_equality(
            model=ref(answer_key_1),
            compare_model=ref(table_name),
            compare_columns=cols_to_include,
            exclude_columns=cols_to_exclude
        ) }}
    {% endif %}
),

answer_key_2_test as (
    {% if submitted_table is none or answer_key_2_table is none %}
        select 1
    {% else %}
        {{ dbt_utils.test_equality(
            model=ref(answer_key_2),
            compare_model=ref(table_name),
            compare_columns=cols_to_include,
            exclude_columns=cols_to_exclude
        ) }}
    {% endif %}
),



answer_key_1_row_count as (
    select
        'snap__hosts' as seed_table,
        count(*) as row_count
    from answer_key_1_test
),

answer_key_2_row_count as (
    select
        'solution__snap__hosts_alt_1' as seed_table,
        count(*) as row_count
    from answer_key_2_test
),


combined as (
    
    select
        c.seed_table,
        c.row_count,
        t.*
    from answer_key_1_row_count c
    left join answer_key_1_test t
        on 1=1
    
	union all

    select
        c.seed_table,
        c.row_count,
        t.*
    from answer_key_2_row_count c
    left join answer_key_2_test t
        on 1=1
    

),

final as (
    select *, min(row_count) over () min_row_count from combined
)

select * from final where min_row_count != 0 and row_count != 0
