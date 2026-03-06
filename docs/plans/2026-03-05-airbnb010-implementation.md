# airbnb010: SCD2 Snapshot Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a hard ADE-bench task where the agent builds a dbt snapshot for host data, rewires staging to read from it, and creates an analytical model tracking superhost evolution — with a background watchdog simulating live data changes during the agent's session.

**Architecture:** Task uses a background watchdog process (launched from setup.sh) that mutates RAW_HOSTS on each dbt invocation the agent makes. For deterministic testing, test_setup kills the watchdog, drops the snapshot, restores original data, then rebuilds with known mutations and frozen DuckDB timestamps.

**Tech Stack:** dbt-core + dbt-duckdb, DuckDB Python API, bash watchdog with polling loop.

**Design doc:** `docs/plans/2026-03-05-airbnb010-scd2-snapshot-design.md`

---

### Task 1: Create directory structure and solution SQL files

**Files:**
- Create: `tasks/airbnb010/solutions/snap__hosts.sql`
- Create: `tasks/airbnb010/solutions/src_hosts.sql`
- Create: `tasks/airbnb010/solutions/dim_superhost_evolution.sql`

**Step 1: Create directory structure**

```bash
mkdir -p tasks/airbnb010/{solutions,seeds,setup}
```

**Step 2: Write the snapshot definition**

Create `tasks/airbnb010/solutions/snap__hosts.sql`:

```sql
{% snapshot snap__hosts %}
{{
    config(
        target_schema='main',
        unique_key='HOST_ID',
        strategy='timestamp',
        updated_at='UPDATED_AT',
    )
}}

SELECT
    ID AS HOST_ID,
    NAME AS HOST_NAME,
    IS_SUPERHOST,
    CREATED_AT,
    UPDATED_AT
FROM {{ source('airbnb', 'hosts') }}

{% endsnapshot %}
```

**Step 3: Write the modified src_hosts.sql**

This rewires the staging model to read from the snapshot's current records instead of the source directly. Must preserve the same output columns so downstream models (`dim_hosts`, etc.) continue working.

Create `tasks/airbnb010/solutions/src_hosts.sql`:

```sql
{{
	config(
		materialized="table",
		alias="src_hosts",
		schema="main",
		unique_key="HOST_ID"
	)
}}

WITH snap AS (
	SELECT *
	FROM {{ ref('snap__hosts') }}
	WHERE dbt_valid_to IS NULL
)

SELECT
	HOST_ID,
	HOST_NAME,
	IS_SUPERHOST,
	CREATED_AT,
	UPDATED_AT
FROM
	snap
```

**Step 4: Write dim_superhost_evolution.sql**

This model queries the full snapshot history. It must:
- Find every host who has ever had `IS_SUPERHOST = 't'`
- Cast `IS_SUPERHOST` (VARCHAR 't'/'f') to proper BOOLEAN in output
- Compute tenure, account age before first superhost, change count, last change timestamp
- Use window functions over the snapshot's SCD2 history

Create `tasks/airbnb010/solutions/dim_superhost_evolution.sql`:

```sql
{{
    config(
        materialized="table",
        alias="dim_superhost_evolution",
        schema="main"
    )
}}

WITH snapshot_history AS (
    SELECT
        HOST_ID,
        HOST_NAME,
        IS_SUPERHOST,
        CREATED_AT,
        dbt_valid_from,
        dbt_valid_to,
        LAG(IS_SUPERHOST) OVER (
            PARTITION BY HOST_ID ORDER BY dbt_valid_from
        ) AS prev_superhost_status
    FROM {{ ref('snap__hosts') }}
),

status_changes AS (
    SELECT
        HOST_ID,
        IS_SUPERHOST,
        dbt_valid_from,
        dbt_valid_to,
        prev_superhost_status,
        CASE
            WHEN prev_superhost_status IS NULL THEN 0
            WHEN IS_SUPERHOST != prev_superhost_status THEN 1
            ELSE 0
        END AS is_change
    FROM snapshot_history
),

host_metrics AS (
    SELECT
        HOST_ID,
        SUM(is_change) AS status_change_count,
        MAX(CASE WHEN is_change = 1 THEN dbt_valid_from END) AS last_status_change_at
    FROM status_changes
    GROUP BY HOST_ID
),

ever_superhost AS (
    SELECT DISTINCT HOST_ID
    FROM snapshot_history
    WHERE IS_SUPERHOST = 't'
),

first_superhost AS (
    SELECT
        HOST_ID,
        MIN(dbt_valid_from) AS first_superhost_at
    FROM snapshot_history
    WHERE IS_SUPERHOST = 't'
    GROUP BY HOST_ID
),

current_state AS (
    SELECT
        HOST_ID,
        HOST_NAME,
        IS_SUPERHOST,
        CREATED_AT,
        dbt_valid_from AS current_valid_from
    FROM snapshot_history
    WHERE dbt_valid_to IS NULL
),

current_superhost_start AS (
    SELECT
        sh.HOST_ID,
        sh.dbt_valid_from AS current_stint_start
    FROM snapshot_history sh
    WHERE sh.IS_SUPERHOST = 't'
      AND sh.dbt_valid_to IS NULL
)

SELECT
    es.HOST_ID,
    (cs.IS_SUPERHOST = 't') AS is_currently_superhost,
    CASE
        WHEN cs.IS_SUPERHOST = 't'
        THEN CAST(DATE_DIFF('day', css.current_stint_start, NOW()) AS INTEGER)
        ELSE NULL
    END AS current_superhost_tenure,
    CAST(DATE_DIFF('day', cs.CREATED_AT, fs.first_superhost_at) AS INTEGER)
        AS acct_age_before_achieving_superhost,
    COALESCE(hm.status_change_count, 0) AS status_change_count,
    hm.last_status_change_at
FROM ever_superhost es
JOIN current_state cs ON es.HOST_ID = cs.HOST_ID
JOIN first_superhost fs ON es.HOST_ID = fs.HOST_ID
LEFT JOIN host_metrics hm ON es.HOST_ID = hm.HOST_ID
LEFT JOIN current_superhost_start css ON es.HOST_ID = css.HOST_ID
ORDER BY es.HOST_ID
```

**Note:** The `NOW()` call will be frozen by the DuckDB macro override during test_setup, making `current_superhost_tenure` deterministic.

**Step 5: Commit**

```bash
git add tasks/airbnb010/solutions/
git commit -m "feat(airbnb010): add solution SQL files for SCD2 snapshot task"
```

---

### Task 2: Write the watchdog and mutation scripts

**Files:**
- Create: `tasks/airbnb010/setup/watchdog.sh`
- Create: `tasks/airbnb010/setup/mutate_hosts.py`
- Create: `tasks/airbnb010/setup/deterministic_mutate.py`

**Step 1: Write watchdog.sh**

This polls manifest.json for mtime changes and triggers mutations. Uses a retry loop on the Python mutation script to handle DuckDB lock contention (dbt holds exclusive lock during runs; watchdog connects after dbt releases it).

Create `tasks/airbnb010/setup/watchdog.sh`:

```bash
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
```

Note: The `LAST_MOD != 0` check skips the first detection (the initial `dbt run` from setup.sh), so mutations only start after the agent's first dbt invocation.

**Step 2: Write mutate_hosts.py (random mode)**

Create `tasks/airbnb010/setup/mutate_hosts.py`:

```python
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
        host_ids = [r[0] for r in conn.execute(
            "SELECT ID FROM raw_hosts WHERE IS_SUPERHOST IS NOT NULL ORDER BY ID"
        ).fetchall()]

        # Pick 300 random hosts
        sample = random.sample(host_ids, min(BATCH_SIZE, len(host_ids)))

        for host_id in sample:
            changes = []
            # Randomly flip IS_SUPERHOST (always)
            changes.append(
                "IS_SUPERHOST = CASE WHEN IS_SUPERHOST = 't' THEN 'f' ELSE 't' END"
            )
            # Randomly change HOST_NAME (~30% of the time)
            if random.random() < 0.3:
                suffix = random.randint(1000, 9999)
                changes.append(f"NAME = NAME || ' ({suffix})'")

            changes.append("UPDATED_AT = CURRENT_TIMESTAMP")

            conn.execute(
                f"UPDATE raw_hosts SET {', '.join(changes)} WHERE ID = ?",
                [host_id]
            )

        conn.close()
        print(f"Mutated {len(sample)} hosts successfully")
        break
    except Exception as e:
        print(f"Attempt {attempt + 1}/{MAX_RETRIES} failed: {e}")
        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_DELAY)
        else:
            print("Max retries reached, skipping this mutation")
```

**Step 3: Write deterministic_mutate.py (test mode)**

Create `tasks/airbnb010/setup/deterministic_mutate.py`:

```python
"""Apply deterministic mutations for test_setup. Two phases:
Phase 1: Flip first 200 hosts by ID, set UPDATED_AT = '2024-06-01'
Phase 2: Re-flip first 100 of those + flip next 100 new, set UPDATED_AT = '2025-01-01'
"""
import argparse
import duckdb

DB_PATH = "/app/airbnb.duckdb"


def get_ordered_host_ids(conn):
    """Get all host IDs ordered by ID where IS_SUPERHOST is not null."""
    return [r[0] for r in conn.execute(
        "SELECT ID FROM raw_hosts WHERE IS_SUPERHOST IS NOT NULL ORDER BY ID"
    ).fetchall()]


def flip_hosts(conn, host_ids, updated_at):
    """Flip IS_SUPERHOST for given host IDs and set UPDATED_AT."""
    if not host_ids:
        return
    placeholders = ", ".join(["?"] * len(host_ids))
    conn.execute(f"""
        UPDATE raw_hosts
        SET IS_SUPERHOST = CASE WHEN IS_SUPERHOST = 't' THEN 'f' ELSE 't' END,
            UPDATED_AT = TIMESTAMP '{updated_at}'
        WHERE ID IN ({placeholders})
    """, host_ids)
    print(f"Flipped {len(host_ids)} hosts, UPDATED_AT = {updated_at}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", type=int, required=True, choices=[1, 2])
    args = parser.parse_args()

    conn = duckdb.connect(DB_PATH)
    host_ids = get_ordered_host_ids(conn)

    if args.phase == 1:
        # Flip first 200 hosts
        flip_hosts(conn, host_ids[:200], "2024-06-01 00:00:00")

    elif args.phase == 2:
        # Re-flip first 100 (back to original) + flip next 100 (201-300)
        phase2_ids = host_ids[:100] + host_ids[200:300]
        flip_hosts(conn, phase2_ids, "2025-01-01 00:00:00")

    conn.close()


if __name__ == "__main__":
    main()
```

**Step 4: Commit**

```bash
git add tasks/airbnb010/setup/
git commit -m "feat(airbnb010): add watchdog and mutation scripts"
```

---

### Task 3: Write setup.sh

**Files:**
- Create: `tasks/airbnb010/setup.sh`

**Step 1: Write setup.sh**

This runs before the agent starts. It:
1. Does normal dbt setup
2. Backs up RAW_HOSTS to CSV
3. Copies watchdog/mutation scripts to /tmp/
4. Launches the watchdog in the background

Create `tasks/airbnb010/setup.sh`:

```bash
#!/bin/bash

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
```

**Step 2: Commit**

```bash
git add tasks/airbnb010/setup.sh
git commit -m "feat(airbnb010): add setup.sh with watchdog launcher"
```

---

### Task 4: Write task.yaml and solution.sh

**Files:**
- Create: `tasks/airbnb010/task.yaml`
- Create: `tasks/airbnb010/solution.sh`

**Step 1: Write task.yaml**

The `test_setup` field contains the full deterministic test sequence: kill watchdog, drop snapshot, restore data, run 3 snapshot layers with frozen timestamps, build models.

Create `tasks/airbnb010/task.yaml`:

```yaml
task_id: airbnb010
status: ready
description: Create an SCD2 snapshot for hosts and build a superhost evolution model.
notes: |-
  Background watchdog mutates RAW_HOSTS on each dbt invocation to simulate
  a live source. test_setup rebuilds deterministically with frozen timestamps.
prompts:
  - key: base
    prompt: |-
      I want you to start snapshotting the hosts table as `snap__hosts` so that we capture changes over time. Then change the staging model to be a view of the latest data so that the rest of the downstream models continue to work as-is. Also make a `dim_superhost_evolution` model which shows each host_id who has ever been a superhost. It should have `is_currently_superhost`, `current_superhost_tenure` (in days), `acct_age_before_achieving_superhost` (for first time), `status_change_count`, `last_status_change_at`.
author_name: test
author_email: test
difficulty: hard
tags:
  - dbt
  - dbt-snapshots
  - scd2
  - model-creation
  - model-refactor

test_setup: |-
  # Kill the background watchdog
  kill $(cat /tmp/watchdog.pid) 2>/dev/null || true
  sleep 1

  # Drop agent's snapshot table and restore original data
  python3 -c "
  import duckdb
  conn = duckdb.connect('/app/airbnb.duckdb')
  conn.execute('DROP TABLE IF EXISTS main.snap__hosts')
  conn.execute('DELETE FROM raw_hosts')
  conn.execute(\"INSERT INTO raw_hosts SELECT * FROM read_csv_auto('/tmp/original_hosts.csv')\")
  conn.close()
  "

  # Layer 1: Snapshot original state (frozen at 2024-01-01)
  python3 -c "
  import duckdb
  conn = duckdb.connect('/app/airbnb.duckdb')
  conn.execute(\"CREATE OR REPLACE MACRO now() AS TIMESTAMP '2024-01-01 00:00:00'\")
  conn.close()
  "
  dbt snapshot

  # Mutation phase 1: Flip first 200 hosts
  python3 /tmp/deterministic_mutate.py --phase 1

  # Layer 2: Capture phase 1 changes (frozen at 2024-06-01)
  python3 -c "
  import duckdb
  conn = duckdb.connect('/app/airbnb.duckdb')
  conn.execute(\"CREATE OR REPLACE MACRO now() AS TIMESTAMP '2024-06-01 00:00:00'\")
  conn.close()
  "
  dbt snapshot

  # Mutation phase 2: Re-flip 100 of original 200 + flip 100 new
  python3 /tmp/deterministic_mutate.py --phase 2

  # Layer 3: Capture phase 2 changes (frozen at 2025-01-01)
  python3 -c "
  import duckdb
  conn = duckdb.connect('/app/airbnb.duckdb')
  conn.execute(\"CREATE OR REPLACE MACRO now() AS TIMESTAMP '2025-01-01 00:00:00'\")
  conn.close()
  "
  dbt snapshot

  # Freeze "today" for tenure/age calculations, build models
  python3 -c "
  import duckdb
  conn = duckdb.connect('/app/airbnb.duckdb')
  conn.execute(\"CREATE OR REPLACE MACRO now() AS TIMESTAMP '2025-06-01 00:00:00'\")
  conn.close()
  "
  dbt run --select dim_superhost_evolution

solution_seeds:
  - table_name: snap__hosts
    exclude_columns:
      - dbt_scd_id
  - table_name: dim_superhost_evolution

variants:
- db_type: duckdb
  db_name: airbnb
  project_type: dbt
  project_name: airbnb
```

**Step 2: Write solution.sh**

Create `tasks/airbnb010/solution.sh`:

```bash
#!/bin/bash
SOLUTIONS_DIR="$(dirname "$(readlink -f "${BASH_SOURCE}")")/solutions"

## Update schema config in solution files by db type
if [[ "$*" == *"--db-type=duckdb"* ]]; then
    replace='schema="main"'
else
    replace='schema="public"'
fi

for file in src_hosts.sql dim_superhost_evolution.sql; do
    find='schema="main"'
    sed -i "s/${find}/${replace}/g" "$SOLUTIONS_DIR/$file"
done

# Copy snapshot definition
mkdir -p snapshots
cp "$SOLUTIONS_DIR/snap__hosts.sql" snapshots/snap__hosts.sql

# Copy modified staging model (overwrites existing)
cp "$SOLUTIONS_DIR/src_hosts.sql" models/source/src_hosts.sql

# Copy analytical model
cp "$SOLUTIONS_DIR/dim_superhost_evolution.sql" models/dim/dim_superhost_evolution.sql

# Run snapshot then models
dbt snapshot
dbt run
```

**Step 3: Commit**

```bash
git add tasks/airbnb010/task.yaml tasks/airbnb010/solution.sh
git commit -m "feat(airbnb010): add task.yaml and solution.sh"
```

---

### Task 5: Generate solution seeds and validate end-to-end

Seeds are generated by running the sage agent with the `--seed` flag, as documented in CONTRIBUTING.md. This runs the solution inside Docker and exports the result tables as CSVs.

**Step 1: Run sage agent with --seed to generate seed CSVs**

```bash
ade run airbnb010 --db duckdb --agent sage --project-type dbt --seed
```

This will:
1. Build the Docker container
2. Run setup.sh (launches watchdog)
3. Run solution.sh (sage agent applies the solution)
4. Run test_setup (kills watchdog, rebuilds deterministically with frozen timestamps)
5. Run tests (will fail on first run since seeds don't exist yet)
6. Export `solution__snap__hosts.csv` and `solution__dim_superhost_evolution.csv` to `tasks/airbnb010/seeds/`

**Step 2: Verify seed data looks correct**

```bash
head -5 tasks/airbnb010/seeds/solution__dim_superhost_evolution.csv
wc -l tasks/airbnb010/seeds/solution__snap__hosts.csv
wc -l tasks/airbnb010/seeds/solution__dim_superhost_evolution.csv
```

Verify:
- snap__hosts has ~14,512 lines (14,511 rows + header)
- dim_superhost_evolution has a reasonable count (~2,000+ rows)
- `is_currently_superhost` column contains boolean values (true/false)
- Columns look correct

**Step 3: Run again WITHOUT --seed to verify tests pass**

```bash
ade run airbnb010 --db duckdb --agent sage --project-type dbt
```

All 4 AUTO tests (existence + equality for both tables) should pass.

**Step 4: Debug and fix any issues**

If tests fail:
- Check experiment logs for error details
- Common issues: SQL syntax errors in dim_superhost_evolution, timestamp mismatches, column type mismatches (boolean vs varchar)
- Fix the solution SQL, re-run with `--seed`, then re-run without

**Step 5: Commit seeds**

```bash
git add tasks/airbnb010/seeds/
git commit -m "feat(airbnb010): add solution seed CSVs"
```

---

### Task 6: Final review and commit

**Step 1: Review the complete task directory**

```bash
find tasks/airbnb010/ -type f | sort
```

Expected:
```
tasks/airbnb010/seeds/_no-op.txt
tasks/airbnb010/seeds/solution__dim_superhost_evolution.csv
tasks/airbnb010/seeds/solution__snap__hosts.csv
tasks/airbnb010/setup.sh
tasks/airbnb010/setup/deterministic_mutate.py
tasks/airbnb010/setup/mutate_hosts.py
tasks/airbnb010/setup/watchdog.sh
tasks/airbnb010/solution.sh
tasks/airbnb010/solutions/dim_superhost_evolution.sql
tasks/airbnb010/solutions/snap__hosts.sql
tasks/airbnb010/solutions/src_hosts.sql
tasks/airbnb010/task.yaml
```

Note: AUTO test files and `_no-op.txt` are generated automatically by ADE-bench. No manual test files needed.

**Step 2: Final commit**

```bash
git add tasks/airbnb010/
git commit -m "feat(airbnb010): complete SCD2 snapshot task for superhost evolution"
```
