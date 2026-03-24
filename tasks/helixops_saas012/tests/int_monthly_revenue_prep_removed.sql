-- Passes only when int_monthly_revenue_prep has been removed from the project.
-- If the model file still exists, it will appear in graph.nodes and this test fails.
{% if 'model.helixops_saas.int_monthly_revenue_prep' in graph.nodes %}
    select 1
{% else %}
    select 1 where 1=0
{% endif %}
