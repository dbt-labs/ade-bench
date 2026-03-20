#!/bin/bash
patch -p1 < /app/setup/changes.patch

# Run dbt to create the models
dbt deps
dbt run
