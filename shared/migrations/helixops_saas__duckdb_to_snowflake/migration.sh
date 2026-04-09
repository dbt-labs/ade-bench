#!/bin/bash
patch -p1 < "/app/migrations/migration.patch"
dbt run --full-refresh
