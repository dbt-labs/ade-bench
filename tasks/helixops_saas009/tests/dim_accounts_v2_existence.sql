-- Passes when dim_accounts v2 and the solution seed both exist.
{% set actual_rel = load_relation(ref('dim_accounts', v=2)) %}
{% set seed_rel = load_relation(ref('solution__dim_accounts_v2')) %}
{% if actual_rel is none or seed_rel is none %}
    select 1
{% else %}
    select 1 where 1=0
{% endif %}
