-- db: snowflake


with matches as (
  select
    count(case when table_name = 'DIMENSION_CUSTOMER' then 1 else null end) as dimension_customer_count,
    count(case when table_name = 'STG_CUSTOMER' then 1 else null end) as stg_customer_count
  from information_schema.tables
  where table_schema not in ('INFORMATION_SCHEMA')
  and table_name in ('DIMENSION_CUSTOMER','STG_CUSTOMER')
)

select *
from matches
where dimension_customer_count != 1
or stg_customer_count != 1