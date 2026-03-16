{% snapshot snap__hosts %}
{{
    config(
        target_schema='main',
        unique_key='ID',
        strategy='timestamp',
        updated_at='UPDATED_AT',
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
