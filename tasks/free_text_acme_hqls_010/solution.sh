#!/bin/bash
cat > models/result.sql << 'GOLD_SQL'
SELECT COUNT(*) AS NoOfPolicy
FROM policy
GOLD_SQL

dbt run --select result
