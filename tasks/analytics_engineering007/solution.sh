#!/bin/bash
set -euo pipefail
## Copy solution model files
patch -p1 < /sage/solutions/changes.patch
