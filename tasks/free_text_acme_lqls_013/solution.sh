#!/bin/bash
cat > models/result.sql << 'GOLD_SQL'
select policy_number, policy_amount
from 
    policy 
    inner join policy_amount on policy.policy_identifier = policy_amount.policy_identifier
    inner join premium on premium.policy_amount_identifier = policy_amount.policy_amount_identifier
GOLD_SQL

dbt run --select result
