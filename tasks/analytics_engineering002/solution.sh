#!/bin/bash
set -euo pipefail

# Add the comma back
patch -p1 < /sage/solutions/changes.patch
