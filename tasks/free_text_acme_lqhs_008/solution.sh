#!/bin/bash
cat > models/result.sql << 'GOLD_SQL'
SELECT
    apr2.party_identifier as AgentID,
    apr1.party_identifier as PolicyHolderID, 
    policy_number,
    policy_amount as premium, 
    company_claim_number,
    ca_lp.claim_amount as Loss_Payment_Amount,  
    ca_lr.claim_amount as Loss_Reserve_Amount,
    ca_ep.claim_amount as Expense_Payment_Amount,
    ca_er.claim_amount as Expense_Reserve_Amount
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
    inner join policy_amount on policy_coverage_detail.policy_coverage_detail_identifier = policy_amount.policy_coverage_detail_identifier
    inner join  agreement_party_role apr1 on apr1.agreement_identifier = policy.policy_identifier
    inner join  agreement_party_role apr2 on apr2.agreement_identifier = policy.policy_identifier
    inner join premium on premium.policy_amount_identifier = policy_amount.policy_amount_identifier
where apr1.party_role_code = 'PH' and apr2.party_role_code = 'AG'
GOLD_SQL

dbt run --select result
