{% set model_name = 'fct_reviews' %}
{% set node = graph.nodes["model." ~ project_name ~ "." ~ model_name] %}
{% set mat = node.config.materialized %}

{% if mat != 'incremental' %}
    select 'Model is not incremental' as error_message
{% else %}
    select 1 where false
{% endif %}