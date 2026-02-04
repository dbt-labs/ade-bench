-- Override default schema name generation to force all models into target schema
-- This prevents the intercom package from creating models in PUBLIC_stg_intercom
-- and PUBLIC_intercom schemas instead of PUBLIC
{% macro generate_schema_name(custom_schema_name, node) %}
    {{ target.schema }}
{% endmacro %}
