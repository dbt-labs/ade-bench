#!/bin/bash
set -euo pipefail

# 1. Normal dbt setup
dbt deps
dbt run

# 2. Backup original RAW_HOSTS for later restoration by test_setup
python3 -c "
import duckdb
conn = duckdb.connect('/app/airbnb.duckdb')
conn.execute(\"COPY raw_hosts TO '/tmp/original_hosts.csv' (HEADER, DELIMITER ',')\")
conn.close()
print('Backed up RAW_HOSTS to /tmp/original_hosts.csv')
"

# 3. Copy scripts to /tmp/ (setup/ dir gets deleted by harness after setup.sh runs)
SETUP_DIR="$(dirname "$(readlink -f "${BASH_SOURCE}")")/setup"
cp "$SETUP_DIR/watchdog.sh" /tmp/watchdog.sh
cp "$SETUP_DIR/mutate_hosts.py" /tmp/mutate_hosts.py
cp "$SETUP_DIR/deterministic_mutate.py" /tmp/deterministic_mutate.py

# 4. Launch watchdog in background
nohup bash /tmp/watchdog.sh > /tmp/watchdog.log 2>&1 &
echo $! > /tmp/watchdog.pid
disown

echo "Watchdog launched with PID $(cat /tmp/watchdog.pid)"
