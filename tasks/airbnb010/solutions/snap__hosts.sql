{% snapshot snap__hosts %}
{{
    config(
        target_schema='main',
        unique_key='HOST_ID',
        strategy='timestamp',
        updated_at='UPDATED_AT',
    )
}}

SELECT
    ID AS HOST_ID,
    NAME AS HOST_NAME,
    IS_SUPERHOST,
    CREATED_AT,
    UPDATED_AT
FROM {{ source('airbnb', 'hosts') }}

{% endsnapshot %}
