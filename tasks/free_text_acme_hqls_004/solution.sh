#!/bin/bash
cat > models/result.sql << 'GOLD_SQL'
SELECT
    SUM(policy_amount)/COUNT(DISTINCT policy_number) AS avgPolicySize
FROM
   policy_coverage_detail 
    inner join policy on policy.policy_identifier = policy_coverage_detail.policy_identifier
    inner join policy_amount on policy_coverage_detail.policy_coverage_detail_identifier = policy_amount.policy_coverage_detail_identifier
    inner join premium on premium.policy_amount_identifier = policy_amount.policy_amount_identifier

GOLD_SQL

dbt run --select result
