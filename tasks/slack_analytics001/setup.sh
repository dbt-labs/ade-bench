#!/bin/bash

dbt deps

# Makes sure fct table doesn't get created in the db
dbt run --select +dim_slack_messages 

# Remove the facts folder and all its contents
rm -rf models/facts