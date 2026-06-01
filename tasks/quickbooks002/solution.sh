#!/bin/bash
set -euo pipefail
## Remove the using_department variable and its references
patch -p1 < /sage/solutions/changes.patch
