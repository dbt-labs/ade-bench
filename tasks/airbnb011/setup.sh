#!/bin/bash
set -euo pipefail

# 1. Install deps
dbt deps

# 2. Corrupt UPDATED_AT before building models so bad timestamps flow through everywhere
python3 -c "
import duckdb
conn = duckdb.connect('/app/airbnb.duckdb')
conn.execute(\"UPDATE raw_hosts SET UPDATED_AT = TIMESTAMP '1980-01-01 00:00:00'\")
conn.close()
print('Corrupted UPDATED_AT to 1980-01-01 for all hosts')
"

# 3. Build models with corrupted data
dbt run

# 4. Backup corrupted RAW_HOSTS for later restoration by test_setup
python3 -c "
import duckdb
conn = duckdb.connect('/app/airbnb.duckdb')
conn.execute(\"COPY raw_hosts TO '/tmp/original_hosts.csv' (HEADER, DELIMITER ',')\")
conn.close()
print('Backed up RAW_HOSTS to /tmp/original_hosts.csv')
"

# 5. Copy scripts to /tmp/ (setup/ dir gets deleted by harness after setup.sh runs)
SETUP_DIR="$(dirname "$(readlink -f "${BASH_SOURCE}")")/setup"
cp "$SETUP_DIR/watchdog.sh" /tmp/watchdog.sh
cp "$SETUP_DIR/mutate_hosts.py" /tmp/mutate_hosts.py
cp "$SETUP_DIR/deterministic_mutate.py" /tmp/deterministic_mutate.py

# 6. Launch watchdog in background
nohup bash /tmp/watchdog.sh > /tmp/watchdog.log 2>&1 &
echo $! > /tmp/watchdog.pid
disown

echo "Watchdog launched with PID $(cat /tmp/watchdog.pid)"
