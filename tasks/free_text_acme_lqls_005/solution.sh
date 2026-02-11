#!/bin/bash
cat > models/result.sql << 'GOLD_SQL'
select policy_number, policy_coverage_detail.effective_date, policy_coverage_detail.expiration_date, policy_amount
from 
    policy 
    inner join policy_coverage_detail on policy.policy_identifier = policy_coverage_detail.policy_identifier
    inner join policy_amount on policy_coverage_detail.policy_coverage_detail_identifier = policy_amount.policy_coverage_detail_identifier
    inner join premium on premium.policy_amount_identifier = policy_amount.policy_amount_identifier
GOLD_SQL

dbt run --select result
