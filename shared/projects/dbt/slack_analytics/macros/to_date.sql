{% macro to_date(timestamp, localize=True, timezone=var('local_timezone')) %}
    {{ return(adapter.dispatch('to_date', 'slack_analytics')(timestamp, localize, timezone)) }}
{% endmacro %}

{% macro default__to_date(timestamp, localize, timezone) %}
    {% if localize %}
    TO_DATE(FROM_UTC_TIMESTAMP({{ timestamp }}, '{{ timezone }}'))
    {% else %}
    TO_DATE({{ timestamp }})
    {% endif %}
{% endmacro %}

{% macro duckdb__to_date(timestamp, localize, timezone) %}
    {% if localize %}
    CAST(timezone('{{ timezone }}', {{ timestamp }}::TIMESTAMPTZ) AS DATE)
    {% else %}
    CAST({{ timestamp }} AS DATE)
    {% endif %}
{% endmacro %}

{% macro snowflake__to_date(timestamp, localize, timezone) %}
    {% if localize %}
    TO_DATE(CONVERT_TIMEZONE('UTC', '{{ timezone }}', {{ timestamp }}))
    {% else %}
    TO_DATE({{ timestamp }})
    {% endif %}
{% endmacro %}
