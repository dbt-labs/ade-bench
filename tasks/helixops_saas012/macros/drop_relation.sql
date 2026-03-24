{% macro drop_relation(schema, identifier, type='view') %}
    {% set relation = api.Relation.create(schema=schema, identifier=identifier, type=type) %}
    {{ adapter.drop_relation(relation) }}
{% endmacro %}
