#!/bin/bash
patch -p1 < "$(dirname "$(readlink -f "${BASH_SOURCE}")")/migration.patch"

# Copy Snowflake-specific solution models that handle epoch-to-timestamp conversion
MIGRATION_DIR="$(dirname "$(readlink -f "${BASH_SOURCE}")")"
cp $MIGRATION_DIR/solutions/stg_quickbooks__refund_receipt.sql solutions/
cp $MIGRATION_DIR/solutions/stg_quickbooks__sales_receipt.sql solutions/
cp $MIGRATION_DIR/solutions/stg_quickbooks__estimate.sql solutions/
