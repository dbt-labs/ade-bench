{{
	config(
		materialized="table",
		alias="src_hosts",
		schema="main",
		unique_key="HOST_ID"
	)
}}

WITH snap AS (
	SELECT *
	FROM {{ ref('snap__hosts') }}
	WHERE dbt_valid_to IS NULL
)

SELECT
	ID AS HOST_ID,
	NAME AS HOST_NAME,
	IS_SUPERHOST,
	CREATED_AT,
	UPDATED_AT
FROM
	snap
