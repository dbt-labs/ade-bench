{{ config(
    partition_by={
        "field": "transaction_created_date",
        "data_type": "date"
    }
) }}

WITH source AS (
    SELECT
        id AS inventory_id,
        transaction_type,
        CAST(STRPTIME(transaction_created_date, '%m/%d/%Y %H:%M:%S') AS DATE) AS transaction_created_date,
        transaction_modified_date,
        product_id,
        quantity,
        purchase_order_id,
        customer_order_id,
        comments
    FROM {{ ref('stg_inventory_transactions') }}
),

unique_source AS (
    SELECT
        *,
        ROW_NUMBER() OVER(PARTITION BY inventory_id ORDER BY inventory_id) AS row_number
    FROM source
)

SELECT
    inventory_id,
    transaction_type,
    transaction_created_date,
    transaction_modified_date,
    product_id,
    quantity,
    purchase_order_id,
    customer_order_id,
    comments
FROM unique_source
WHERE row_number = 1
