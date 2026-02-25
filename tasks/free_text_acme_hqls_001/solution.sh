#!/bin/bash
cat > models/result.sql << 'GOLD_SQL'
select policy_number, count(company_claim_number) as NoOfClaims
from 
    policy 
    inner join policy_coverage_detail on policy.policy_identifier = policy_coverage_detail.policy_identifier
    inner join claim_coverage on claim_coverage.policy_coverage_detail_identifier = policy_coverage_detail.policy_coverage_detail_identifier
    inner join claim on claim.claim_identifier = claim_coverage.claim_identifier
group by policy_number
GOLD_SQL

dbt run --select result
