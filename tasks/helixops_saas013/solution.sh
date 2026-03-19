#!/bin/bash
SOLUTIONS_DIR="$(dirname "$(readlink -f "${BASH_SOURCE}")")/solutions"
cp "$SOLUTIONS_DIR/stg_invoice_line_items.sql" models/staging/stg_invoice_line_items.sql
dbt run --select stg_invoice_line_items+
