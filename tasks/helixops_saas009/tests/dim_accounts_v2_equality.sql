-- Passes when dim_accounts v2 output matches expected solution.
-- Uses versioned ref syntax since dim_accounts_v2 is defined via dbt model versioning.
with actual as (
    select * from {{ ref('dim_accounts', v=2) }}
),
expected as (
    select * from {{ ref('solution__dim_accounts_v2') }}
),
a_minus_b as (
    select * from expected
    except
    select * from actual
),
b_minus_a as (
    select * from actual
    except
    select * from expected
)
select * from a_minus_b
union all
select * from b_minus_a
