#!/bin/bash
cat > models/result.sql << 'GOLD_SQL'
select policy_number, avg(datediff('day', claim_open_date, claim_close_date))
from claim 
inner join claim_coverage on claim.claim_identifier = claim_coverage.claim_identifier
inner join policy_coverage_detail on claim_coverage.policy_coverage_detail_identifier = policy_coverage_detail.policy_coverage_detail_identifier
inner join policy on policy.policy_identifier = policy_coverage_detail.policy_identifier
where claim_close_date IS NOT NULL
group by policy_number

GOLD_SQL

dbt run --select result
