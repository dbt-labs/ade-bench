{% snapshot snap__hosts %}
{{
    config(
        target_schema='main',
        unique_key='ID',
        strategy='check',
        check_cols='all',
    )
}}

SELECT
    ID,
    NAME,
    IS_SUPERHOST,
    CREATED_AT,
    UPDATED_AT
FROM {{ source('airbnb', 'hosts') }}

{% endsnapshot %}
