{{
    config(
        materialized="table",
        alias="dim_superhost_evolution",
        schema="main"
    )
}}

WITH snapshot_history AS (
    SELECT
        ID AS HOST_ID,
        NAME AS HOST_NAME,
        IS_SUPERHOST,
        CREATED_AT,
        dbt_valid_from,
        dbt_valid_to,
        LAG(IS_SUPERHOST) OVER (
            PARTITION BY ID ORDER BY dbt_valid_from
        ) AS prev_superhost_status
    FROM {{ ref('snap__hosts') }}
),

status_changes AS (
    SELECT
        HOST_ID,
        IS_SUPERHOST,
        dbt_valid_from,
        dbt_valid_to,
        prev_superhost_status,
        CASE
            WHEN prev_superhost_status IS NULL THEN 0
            WHEN IS_SUPERHOST != prev_superhost_status THEN 1
            ELSE 0
        END AS is_change
    FROM snapshot_history
),

host_metrics AS (
    SELECT
        HOST_ID,
        SUM(is_change) AS status_change_count,
        MAX(CASE WHEN is_change = 1 THEN dbt_valid_from END) AS last_status_change_at
    FROM status_changes
    GROUP BY HOST_ID
),

ever_superhost AS (
    SELECT DISTINCT HOST_ID
    FROM snapshot_history
    WHERE IS_SUPERHOST = 't'
),

first_superhost AS (
    SELECT
        HOST_ID,
        MIN(dbt_valid_from) AS first_superhost_at
    FROM snapshot_history
    WHERE IS_SUPERHOST = 't'
    GROUP BY HOST_ID
),

current_state AS (
    SELECT
        HOST_ID,
        HOST_NAME,
        IS_SUPERHOST,
        CREATED_AT,
        dbt_valid_from AS current_valid_from
    FROM snapshot_history
    WHERE dbt_valid_to IS NULL
)

SELECT
    es.HOST_ID,
    (cs.IS_SUPERHOST = 't') AS is_currently_superhost,
    CAST(DATE_DIFF('day', cs.CREATED_AT, fs.first_superhost_at) AS INTEGER)
        AS acct_age_before_achieving_superhost,
    COALESCE(hm.status_change_count, 0) AS status_change_count,
    hm.last_status_change_at
FROM ever_superhost es
JOIN current_state cs ON es.HOST_ID = cs.HOST_ID
JOIN first_superhost fs ON es.HOST_ID = fs.HOST_ID
LEFT JOIN host_metrics hm ON es.HOST_ID = hm.HOST_ID
ORDER BY es.HOST_ID
