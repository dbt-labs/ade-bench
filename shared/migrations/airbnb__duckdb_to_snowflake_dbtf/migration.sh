#!/bin/bash
set -euo pipefail
patch -p1 < "/app/migrations/migration.patch"
