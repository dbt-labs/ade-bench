#!/bin/bash
cat > models/result.sql << 'GOLD_SQL'
SELECT
    policy_number,
    company_claim_number,
    catastrophe_name,
    (ca_lp.claim_amount + ca_lr.claim_amount + ca_ep.claim_amount + ca_er.claim_amount) as Loss
FROM
    Claim
    inner join claim_amount ca_lp on claim.claim_identifier = ca_lp.claim_identifier
    inner JOIN loss_payment ON ca_lp.claim_amount_identifier = loss_payment.claim_amount_identifier
    inner join claim_amount ca_lr on claim.claim_identifier = ca_lr.claim_identifier
    inner JOIN loss_reserve ON ca_lr.claim_amount_identifier = loss_reserve.claim_amount_identifier
    inner join claim_amount ca_ep on claim.claim_identifier = ca_ep.claim_identifier
    inner JOIN expense_payment ON ca_ep.claim_amount_identifier = expense_payment.claim_amount_identifier
    inner join claim_amount ca_er on claim.claim_identifier = ca_er.claim_identifier
    inner JOIN expense_reserve ON ca_er.claim_amount_identifier = expense_reserve.claim_amount_identifier
    inner join claim_coverage on claim.claim_identifier = claim_coverage.claim_identifier
    inner join policy_coverage_detail on claim_coverage.policy_coverage_detail_identifier = policy_coverage_detail.policy_coverage_detail_identifier
    inner join policy on policy.policy_identifier = policy_coverage_detail.policy_identifier
    inner join catastrophe on claim.catastrophe_identifier = catastrophe.catastrophe_identifier
    
GOLD_SQL

dbt run --select result
