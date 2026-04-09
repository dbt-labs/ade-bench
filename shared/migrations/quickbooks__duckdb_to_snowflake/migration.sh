#!/bin/bash
patch -p1 < "/app/migrations/migration.patch"

# Copy Snowflake-specific solution models that handle epoch-to-timestamp conversion
cp /app/migrations/solutions/stg_quickbooks__refund_receipt.sql solutions/
cp /app/migrations/solutions/stg_quickbooks__sales_receipt.sql solutions/
cp /app/migrations/solutions/stg_quickbooks__estimate.sql solutions/
