#!/bin/bash
cat > models/result.sql << 'GOLD_SQL'
SELECT
    company_claim_number,
    claim_amount as expense_reserve_amount
FROM
    Claim
    inner join claim_amount on claim.claim_identifier = claim_amount.claim_identifier
    inner JOIN expense_reserve ON claim_amount.claim_amount_identifier = expense_reserve.claim_amount_identifier

GOLD_SQL

dbt run --select result
