#!/bin/bash
patch -p1 < "/app/migrations/migration.patch"

# Patch solution models to use Snowflake epoch-to-timestamp conversion (TO_TIMESTAMP_NTZ)
patch -p1 < "/app/migrations/solutions.patch"
