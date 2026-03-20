#!/bin/bash
## Fix position_desc case sensitivity in finishes_by_driver
patch -p1 < /sage/solutions/changes.patch

# Run dbt to create the models
dbt run --select finishes_by_driver
