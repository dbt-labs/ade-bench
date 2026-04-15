#!/bin/bash
set -euo pipefail

## Remove sources
rm models/core/*.sql

patch -p1 < /app/setup/changes.patch
