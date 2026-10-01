{% macro unnest_array(array_column, alias) %}
    {{ return(adapter.dispatch('unnest_array', 'slack_analytics')(array_column, alias)) }}
{% endmacro %}

{% macro databricks__unnest_array(array_column, alias) %}
    lateral view explode({{ array_column }}) as {{ alias }}
{% endmacro %}

{% macro snowflake__unnest_array(array_column, alias) %}
    , lateral flatten(input => {{ array_column }}) as {{ alias }}
{% endmacro %}

{% macro duckdb__unnest_array(array_column, alias) %}
    , unnest(from_json({{ array_column }}, '["JSON"]')) as t({{ alias }})
{% endmacro %}