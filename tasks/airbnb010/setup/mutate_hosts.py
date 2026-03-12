"""Randomly mutate 300 hosts in RAW_HOSTS to simulate source data refresh."""

import random
import time
import duckdb

DB_PATH = "/app/airbnb.duckdb"
BATCH_SIZE = 300
MAX_RETRIES = 30
RETRY_DELAY = 2

for attempt in range(MAX_RETRIES):
    try:
        conn = duckdb.connect(DB_PATH)

        # Get all host IDs (excluding NULLs in IS_SUPERHOST)
        host_ids = [
            r[0]
            for r in conn.execute(
                "SELECT ID FROM raw_hosts WHERE IS_SUPERHOST IS NOT NULL ORDER BY ID"
            ).fetchall()
        ]

        # Pick 300 random hosts
        sample = random.sample(host_ids, min(BATCH_SIZE, len(host_ids)))

        for host_id in sample:
            changes = []
            # Randomly flip IS_SUPERHOST (always)
            changes.append("IS_SUPERHOST = CASE WHEN IS_SUPERHOST = 't' THEN 'f' ELSE 't' END")
            # Randomly change HOST_NAME (~30% of the time)
            if random.random() < 0.3:
                suffix = random.randint(1000, 9999)
                changes.append(f"NAME = NAME || ' ({suffix})'")

            changes.append("UPDATED_AT = CURRENT_TIMESTAMP")

            conn.execute(f"UPDATE raw_hosts SET {', '.join(changes)} WHERE ID = ?", [host_id])

        conn.close()
        print(f"Mutated {len(sample)} hosts successfully")
        break
    except Exception as e:
        print(f"Attempt {attempt + 1}/{MAX_RETRIES} failed: {e}")
        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_DELAY)
        else:
            print("Max retries reached, skipping this mutation")
