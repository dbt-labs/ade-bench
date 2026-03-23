#!/bin/bash

## Replace all surrogate_key functions with generate_surrogate_key
## and add the global variable to the dbt_project.yml file
patch -p1 < /sage/solutions/changes.patch
