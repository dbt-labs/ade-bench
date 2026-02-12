#!/bin/bash
cat > models/result.sql << 'GOLD_SQL'
select policy_number, policy.effective_date, policy.expiration_date
from policy

GOLD_SQL

dbt run --select result
