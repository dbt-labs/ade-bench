#!/bin/bash

## Fix CTE names in fct_reviews and dim_hosts
patch -p1 < /sage/solutions/changes.patch

dbt deps
