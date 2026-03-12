#!/bin/bash
cat > models/result.sql << 'GOLD_SQL'
select party_identifier, policy_number, sum(policy_amount)
from agreement_party_role
join policy on agreement_party_role.agreement_identifier = policy.policy_identifier
inner join policy_amount on policy.policy_identifier = policy_amount.policy_identifier
inner join premium on premium.policy_amount_identifier = policy_amount.policy_amount_identifier
where agreement_party_role.party_role_code = 'PH'
group by party_identifier, policy_number
GOLD_SQL

dbt run --select result
