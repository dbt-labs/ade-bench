#!/bin/bash
## Change sum back to max in constructor_points and driver_points
patch -p1 < /sage/solutions/changes.patch

# Run dbt to create the models
dbt run --select constructor_points driver_points
