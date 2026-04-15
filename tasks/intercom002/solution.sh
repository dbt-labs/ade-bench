#!/bin/bash
set -euo pipefail
# Create intercom__threads and intercom__conversation_metrics models
patch -p1 < /sage/solutions/changes.patch

dbt deps
