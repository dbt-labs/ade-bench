-- Passes only when dim_accounts is properly defined with dbt model versioning (both v1 and v2 in graph).
-- Node key format for versioned models: model.project.model_name.vN
{% if 'model.helixops_saas.dim_accounts.v1' in graph.nodes
   and 'model.helixops_saas.dim_accounts.v2' in graph.nodes %}
    select 1 where 1=0
{% else %}
    select 1
{% endif %}
