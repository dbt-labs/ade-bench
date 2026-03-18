{% macro strip_numeric(col) -%}
regexp_replace(cast({{ col }} as varchar), '[^0-9\.-]', '', 'g')
{%- endmacro %}

{% macro integer_from_text(col) -%}
try_cast(nullif({{ strip_numeric(col) }}, '') as integer)
{%- endmacro %}

{% macro numeric_from_text(col) -%}
try_cast(nullif({{ strip_numeric(col) }}, '') as double)
{%- endmacro %}

{% macro epoch_to_timestamp(col) -%}
case
  when {{ col }} is null then null
  when lower(trim(cast({{ col }} as varchar))) in ('', 'null', 'n/a', 'na') then null
  else to_timestamp(try_cast(regexp_replace(trim(cast({{ col }} as varchar)), '\.[0-9]+$', '') as bigint))::timestamp
end
{%- endmacro %}

{% macro bool_from_text(col) -%}
case
  when lower(trim(cast({{ col }} as varchar))) in ('y', 'yes', '1', 'true', 't') then true
  when lower(trim(cast({{ col }} as varchar))) in ('n', 'no', '0', 'false', 'f') then false
  else null
end
{%- endmacro %}
