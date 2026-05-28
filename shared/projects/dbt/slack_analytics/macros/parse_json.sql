{% macro parse_json(column_name) %}
    {{ return(adapter.dispatch('parse_json', 'slack_analytics')(column_name)) }}
{% endmacro %}

{% macro default__parse_json(column_name) %}
    {{ column_name }}::JSON
{% endmacro %}

{% macro databricks__parse_json(column_name) %}
    FROM_JSON({{ column_name }}, 'STRING')
{% endmacro %}

{% macro snowflake__parse_json(column_name) %}
    PARSE_JSON({{ column_name }})
{% endmacro %}