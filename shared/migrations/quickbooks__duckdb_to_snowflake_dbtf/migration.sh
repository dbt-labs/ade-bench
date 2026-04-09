#!/bin/bash
patch -p1 < "/app/migrations/migration.patch"

# Copy Snowflake-specific solution models that handle epoch-to-timestamp conversion
MIGRATION_DIR="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"
cp $MIGRATION_DIR/solutions/stg_quickbooks__refund_receipt.sql solutions/ 2>/dev/null || true
cp $MIGRATION_DIR/solutions/stg_quickbooks__sales_receipt.sql solutions/ 2>/dev/null || true
cp $MIGRATION_DIR/solutions/stg_quickbooks__estimate.sql solutions/ 2>/dev/null || true
