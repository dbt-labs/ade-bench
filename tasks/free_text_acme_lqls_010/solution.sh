#!/bin/bash
cat > models/result.sql << 'GOLD_SQL'
SELECT company_claim_number, claim_open_date, claim_close_date
FROM claim

GOLD_SQL

dbt run --select result
