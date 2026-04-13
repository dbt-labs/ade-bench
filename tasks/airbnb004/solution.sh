#!/bin/bash
## Add the primary key to the fct_reviews model
patch -p1 < /sage/solutions/changes.patch

# Run dbt to create the models
dbt run --select fct_reviews --full-refresh
