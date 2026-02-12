{% set models = [
    "stg_asana__project_task",
    "stg_asana__project",
    "stg_asana__section",
    "stg_asana__story",
    "stg_asana__tag",
    "stg_asana__task_follower",
    "stg_asana__task_section",
    "stg_asana__task_tag",
    "stg_asana__task",
    "stg_asana__team",
    "stg_asana__user"
] %}

{% for model in models %}
    {% set model_node = graph.nodes["model.asana_source." ~ model] %}
    {% set model_refs = model_node.refs %}
    {% set model_sources = model_node.sources %}

    {% if model_refs | length != 0 or model_sources | length == 0 %}
        select '{{ model }} not updated correctly' as error_message
    {% else %}
        select 1 where false
    {% endif %}
    {% if not loop.last %}
        union all
    {% endif %}
{% endfor %}