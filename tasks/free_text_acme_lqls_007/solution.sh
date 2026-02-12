#!/bin/bash
cat > models/result.sql << 'GOLD_SQL'
select policy.policy_number, party_identifier as agentid
from agreement_party_role
join policy on agreement_party_role.agreement_identifier = policy.policy_identifier
where agreement_party_role.party_role_code = 'AG'
GOLD_SQL

dbt run --select result
