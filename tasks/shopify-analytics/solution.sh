#!/bin/bash
# Create the product_performance and daily_shop_performance models
patch -p1 < /sage/solutions/changes.patch

dbt deps

# Run dbt to create the models
dbt run --select product_performance daily_shop_performance
