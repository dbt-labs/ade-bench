#!/bin/bash
set -euo pipefail

echo "Setup Deep Agents Code"
uv tool install --prerelease=allow deepagents-code==0.1.45
export PATH="/root/.local/bin:${PATH}"
dcode --version
