#!/bin/bash
python3 -c "
import duckdb
conn = duckdb.connect('/app/helixops_saas.duckdb')
conn.execute(\"UPDATE raw_invoice_line_items SET recurring_hint = 'Y' WHERE line_id IN ('L7102', 'L7220', 'L7342')\")
conn.close()
print('Updated recurring_hint for onboarding line items L7102, L7220, L7342')
"
dbt run --select stg_invoice_line_items int_invoice_finance fct_monthly_revenue
