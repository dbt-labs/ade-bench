{% snapshot snap__hosts %}
{{
    config(
        target_schema='main',
        unique_key='HOST_ID',
        strategy='check',
        check_cols='all',
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
