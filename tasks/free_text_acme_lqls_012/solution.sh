#!/bin/bash
cat > models/result.sql << 'GOLD_SQL'
SELECT
    company_claim_number,
    claim_amount as Loss_Payment_Amount
FROM
    Claim
    inner join claim_amount on claim.claim_identifier = claim_amount.claim_identifier
    inner JOIN loss_payment ON claim_amount.claim_amount_identifier = loss_payment.claim_amount_identifier

GOLD_SQL

dbt run --select result
