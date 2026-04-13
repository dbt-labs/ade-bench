#!/bin/bash
## Add using_exchange_rate variable and wrap exchange rate columns
patch -p1 < /sage/solutions/changes.patch

if [[ "$*" == *"--db-type=snowflake"* ]]; then
    patch -p1 < /sage/solutions/changes.snowflake.patch
fi
