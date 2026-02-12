#!/bin/bash
cat > models/result.sql << 'GOLD_SQL'
SELECT company_claim_number
FROM claim
where claim_close_date >= '2019-01-01' and claim_close_date <= '2019-12-31'
GOLD_SQL

dbt run --select result
