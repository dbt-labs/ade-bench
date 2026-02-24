{% set model = "results" %}
{% set src_name = "src_" ~ model %}
{% set model_name = "stg_f1_dataset__" ~ model %}
{% set node = graph.nodes["model." ~ project_name ~ "." ~ model_name ] %}
{% set ref_list = node.refs %}

-- Model should have three references
{% if ref_list | length != 3 %}
    select '{{ model_name }} does not have three references' as error_message union all
{% elif 'src_position_descriptions' not in ref_list | map(attribute='name') | list %}
    select '{{ model_name }} does not use src_position_descriptions as source' as error_message union all
{% elif 'src_results' not in ref_list | map(attribute='name') | list %}
    select '{{ model_name }} does not use src_results as source' as error_message union all
{% elif 'src_status' not in ref_list | map(attribute='name') | list %}
    select '{{ model_name }} does not use src_status as source' as error_message union all
{% endif %}

    select 'none' as error_message where false