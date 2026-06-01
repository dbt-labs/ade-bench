#!/bin/bash
set -euo pipefail
# Create the project and profile files
mkdir -p models
patch -p1 < /sage/solutions/changes.patch
