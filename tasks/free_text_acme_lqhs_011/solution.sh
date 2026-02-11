#!/bin/bash
cat > models/result.sql << 'GOLD_SQL'
SELECT
    party_identifier as AgentID,
    policy_number,
    company_claim_number,
    catastrophe_name
FROM
    Claim
    inner join catastrophe on claim.catastrophe_identifier = catastrophe.catastrophe_identifier
    inner join claim_coverage on claim.claim_identifier = claim_coverage.claim_identifier
    inner join policy_coverage_detail on claim_coverage.policy_coverage_detail_identifier = policy_coverage_detail.policy_coverage_detail_identifier
    inner join policy on policy.policy_identifier = policy_coverage_detail.policy_identifier
    inner join  agreement_party_role  on agreement_party_role.agreement_identifier = policy.policy_identifier
where  agreement_party_role.party_role_code = 'AG'
GOLD_SQL

dbt run --select result
