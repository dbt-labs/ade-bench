#!/bin/bash
cat > models/result.sql << 'GOLD_SQL'
SELECT
    company_claim_number,
    (ca_lp.claim_amount + ca_lr.claim_amount ) as LossAmount
FROM
    Claim
    inner join claim_amount ca_lp on claim.claim_identifier = ca_lp.claim_identifier
    inner JOIN loss_payment ON ca_lp.claim_amount_identifier = loss_payment.claim_amount_identifier
    inner join claim_amount ca_lr on claim.claim_identifier = ca_lr.claim_identifier
    inner JOIN loss_reserve ON ca_lr.claim_amount_identifier = loss_reserve.claim_amount_identifier

GOLD_SQL

dbt run --select result
