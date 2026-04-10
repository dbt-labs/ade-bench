#!/bin/bash
patch -p1 --batch < /app/setup/changes.patch || true

if [[ "$*" == *"--db-type=snowflake"* ]]; then
    patch -p1 --batch --forward < /app/setup/changes.snowflake.patch
fi

dbt deps
dbt run
