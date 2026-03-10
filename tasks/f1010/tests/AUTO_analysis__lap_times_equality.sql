-- Define columns to compare
{% set table_name = 'analysis__lap_times' %}
{% set answer_key_1 = 'solution__analysis__lap_times' %}
{% set answer_key_2 = 'solution__analysis__lap_times_exclude_pit_stops' %}


{% set cols_to_include = [
    
] %}

{% set cols_to_exclude = [
    
] %}


-------------------------------------
---- DO NOT EDIT BELOW THIS LINE ----
-- depends_on: {{ ref(table_name) }}
-- depends_on: {{ ref(answer_key_1) }}
-- depends_on: {{ ref(answer_key_2) }}


with

answer_key_1_test as (
    {% if load_relation(ref(table_name)) is none or load_relation(ref(answer_key_1)) is none %}
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
    {% if load_relation(ref(table_name)) is none or load_relation(ref(answer_key_2)) is none %}
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
        'analysis__lap_times' as seed_table,
        count(*) as row_count
    from answer_key_1_test
),

answer_key_2_row_count as (
    select
        'analysis__lap_times_exclude_pit_stops' as seed_table,
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
