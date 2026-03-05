#!/bin/bash
# Watchdog: detects dbt invocations via manifest.json mtime changes
# and triggers random data mutations to simulate a live source.

MANIFEST="/app/target/manifest.json"
LAST_MOD=0

while true; do
    if [ -f "$MANIFEST" ]; then
        CURR_MOD=$(stat -c %Y "$MANIFEST" 2>/dev/null || echo 0)
        if [ "$CURR_MOD" != "0" ] && [ "$CURR_MOD" != "$LAST_MOD" ]; then
            if [ "$LAST_MOD" != "0" ]; then
                echo "$(date): manifest.json changed, triggering mutation" >> /tmp/watchdog.log
                python3 /tmp/mutate_hosts.py >> /tmp/watchdog.log 2>&1
            fi
            LAST_MOD=$CURR_MOD
        fi
    fi
    sleep 2
done
