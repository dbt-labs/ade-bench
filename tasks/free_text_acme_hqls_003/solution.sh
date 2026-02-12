#!/bin/bash
cat > models/result.sql << 'GOLD_SQL'
select  party_identifier as agentid, count(policy.policy_number) as NoOfPolicies
from agreement_party_role
join policy on agreement_party_role.agreement_identifier = policy.policy_identifier
where agreement_party_role.party_role_code = 'AG'
group by party_identifier
GOLD_SQL

dbt run --select result
