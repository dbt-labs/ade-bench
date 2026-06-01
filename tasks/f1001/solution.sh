#!/bin/bash
set -euo pipefail
## Restore src_* model references and update f1_dataset.yml
patch -p1 < /sage/solutions/changes.patch
