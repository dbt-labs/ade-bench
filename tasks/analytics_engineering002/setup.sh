#!/bin/bash
patch -p1 < /app/setup/changes.patch

dbt deps
dbt run
