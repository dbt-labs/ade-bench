#!/bin/bash

# Run dbt to create the models
dbt deps
dbt run
exit 0
