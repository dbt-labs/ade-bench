#!/bin/bash
cat > models/result.sql << 'GOLD_SQL'
SELECT COUNT(*) AS NoOfClaims
FROM claim
GOLD_SQL

dbt run --select result
