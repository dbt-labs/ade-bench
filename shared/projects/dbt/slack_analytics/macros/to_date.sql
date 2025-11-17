{% macro to_date(timestamp, localize=True, timezone=var('local_timezone')) %}
    {% if localize %}
    TO_DATE(FROM_UTC_TIMESTAMP({{ timestamp }}, '{{ timezone }}'))
    {% else %}
    TO_DATE({{ timestamp }})
    {% endif %}
{% endmacro %}