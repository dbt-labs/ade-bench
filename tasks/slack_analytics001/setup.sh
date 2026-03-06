#!/bin/bash
# Remove the facts folder and all its contents
rm -rf models/facts

dbt deps
dbt run