#!/bin/bash
set -euo pipefail

## Replace all surrogate_key functions with generate_surrogate_key
patch -p1 < /sage/solutions/changes.patch

## Add the backwards-compatibility variable to dbt_project.yml
yq -i '.vars.surrogate_key_treat_nulls_as_empty_strings = true' dbt_project.yml
