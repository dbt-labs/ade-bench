# airbnb010: SCD2 Snapshot for Superhost Status

## Summary

New ADE-bench task where the agent must set up a dbt snapshot to track host changes over time, rewire the staging layer to read from the snapshot, and build an analytical model showing superhost evolution.

## Task Prompt

> I want you to start snapshotting the hosts table as `snap__hosts` so that we capture changes over time. Then change the staging model to be a view of the latest data so that the rest of the downstream models continue to work as-is. Also make a `dim_superhost_evolution` model which shows each host_id who has ever been a superhost. It should have `is_currently_superhost`, `current_superhost_tenure` (in days), `acct_age_before_achieving_superhost` (for first time), `status_change_count`, `last_status_change_at`.

## What the Agent Must Do

1. **Create `snapshots/snap__hosts.sql`** — a dbt snapshot using `timestamp` strategy on the hosts source, with `updated_at` pointing at `UPDATED_AT` column. Must choose correct `unique_key` and `target_schema`.

2. **Modify `models/source/src_hosts.sql`** — change it from reading `{{ source('airbnb', 'hosts') }}` to reading from `{{ ref('snap__hosts') }}` filtered to current records (`dbt_valid_to IS NULL`). This keeps the existing DAG intact.

3. **Create `models/dim/dim_superhost_evolution.sql`** — query the full snapshot history to produce one row per host who has ever had `IS_SUPERHOST = 't'`, with columns:
   - `host_id`
   - `is_currently_superhost` — current status
   - `current_superhost_tenure` — integer days since most recent promotion to superhost (NULL if not currently superhost)
   - `acct_age_before_achieving_superhost` — integer days between account creation and first time they became superhost
   - `status_change_count` — integer count of IS_SUPERHOST transitions
   - `last_status_change_at` — timestamp of most recent status change

4. **Run `dbt snapshot` then `dbt run`** to verify everything works.

## Data Simulation: Background Watchdog

### Why
The raw data has no temporal changes (`CREATED_AT == UPDATED_AT` for all 14,111 rows). To make SCD2 meaningful, we simulate a live source that refreshes during the agent's session.

### Mechanism
`setup.sh` launches a background watchdog process that:
- Polls `/app/target/manifest.json` for mtime changes every 2 seconds
- Each detected change (= a dbt invocation) triggers a mutation of 300 random hosts in `RAW_HOSTS`
- Mutations randomly flip `IS_SUPERHOST` and/or change `HOST_NAME`, setting `UPDATED_AT = current real timestamp`
- The agent sees realistic data drift as they work

The watchdog PID is saved to `/tmp/watchdog.pid` for later cleanup:
```bash
nohup bash /tmp/watchdog.sh > /tmp/watchdog.log 2>&1 &
echo $! > /tmp/watchdog.pid
disown
```

### Files written by setup.sh to /tmp/
- `/tmp/watchdog.sh` — polling loop that detects manifest.json changes
- `/tmp/mutate_hosts.py` — Python script that mutates 300 random hosts (random mode)
- `/tmp/deterministic_mutate.py` — Python script for known test mutations (used by test_setup)
- `/tmp/original_hosts.csv` — backup of original RAW_HOSTS for restoration
- `/tmp/watchdog.pid` — PID file for cleanup

## Test Setup: Deterministic Final State

### DuckDB `now()` Override
dbt snapshots use DuckDB's `now()` function (not Python's datetime) for SCD2 timestamps. We override it with a DuckDB macro:

```sql
CREATE OR REPLACE MACRO now() AS TIMESTAMP '2024-01-01 00:00:00';
```

This freezes `dbt_valid_from`, `dbt_valid_to`, and `dbt_updated_at` to known values.

Combined with the `timestamp` strategy using `UPDATED_AT` column: `dbt_valid_from` comes from the source's `UPDATED_AT` (which we control in deterministic mutations), and `dbt_valid_to` for superseded records uses the new record's `UPDATED_AT`. The `now()` override catches any remaining code paths that call `now()` directly.

### test_setup sequence

```bash
# 1. Stop the watchdog
kill $(cat /tmp/watchdog.pid) 2>/dev/null

# 2. Wipe agent's snapshot table
python3 -c "
import duckdb
conn = duckdb.connect('/app/airbnb.duckdb')
conn.execute('DROP TABLE IF EXISTS main.snap__hosts')
"

# 3. Restore original RAW_HOSTS from backup
python3 -c "
import duckdb
conn = duckdb.connect('/app/airbnb.duckdb')
conn.execute('DELETE FROM raw_hosts')
conn.execute(\"INSERT INTO raw_hosts SELECT * FROM read_csv_auto('/tmp/original_hosts.csv')\")
"

# 4. Freeze now() and run Layer 1: Original state
python3 -c "
import duckdb
conn = duckdb.connect('/app/airbnb.duckdb')
conn.execute(\"CREATE OR REPLACE MACRO now() AS TIMESTAMP '2024-01-01 00:00:00'\")
"
dbt snapshot

# 5. Mutation phase 1: Flip first 200 hosts by ID, set UPDATED_AT = '2024-06-01'
python3 /tmp/deterministic_mutate.py --phase 1

# 6. Freeze now() and run Layer 2: Capture phase 1 changes
python3 -c "
import duckdb
conn = duckdb.connect('/app/airbnb.duckdb')
conn.execute(\"CREATE OR REPLACE MACRO now() AS TIMESTAMP '2024-06-01 00:00:00'\")
"
dbt snapshot

# 7. Mutation phase 2: Re-flip first 100 of original 200 + flip 100 new (IDs 201-300)
#    Set UPDATED_AT = '2025-01-01'
python3 /tmp/deterministic_mutate.py --phase 2

# 8. Freeze now() and run Layer 3: Capture phase 2 changes
python3 -c "
import duckdb
conn = duckdb.connect('/app/airbnb.duckdb')
conn.execute(\"CREATE OR REPLACE MACRO now() AS TIMESTAMP '2025-01-01 00:00:00'\")
"
dbt snapshot

# 9. Freeze "today" for tenure/age calculations, then build models
python3 -c "
import duckdb
conn = duckdb.connect('/app/airbnb.duckdb')
conn.execute(\"CREATE OR REPLACE MACRO now() AS TIMESTAMP '2025-06-01 00:00:00'\")
"
dbt run --select dim_superhost_evolution
```

### Deterministic Mutation Details

**Phase 1:** Select first 200 hosts by ID (where `IS_SUPERHOST IS NOT NULL`). Flip `IS_SUPERHOST` ('t'→'f', 'f'→'t'). Set `UPDATED_AT = '2024-06-01 00:00:00'`.

**Phase 2:** Of those 200, re-flip the first 100 (by ID) back to original values. Also select the next 100 hosts by ID (ranks 201-300 when ordered by ID, `IS_SUPERHOST IS NOT NULL`) and flip those. Set `UPDATED_AT = '2025-01-01 00:00:00'`.

### Resulting snapshot state (3 layers)

| Layer | Frozen time | dbt_valid_from source | What changed |
|-------|-------------|----------------------|-------------|
| 1 | 2024-01-01 | Original UPDATED_AT values | Initial state — 14,111 rows, all current |
| 2 | 2024-06-01 | '2024-06-01' (from mutation UPDATED_AT) | 200 hosts flipped — 200 old closed, 200 new |
| 3 | 2025-01-01 | '2025-01-01' (from mutation UPDATED_AT) | 100 re-flipped + 100 new — 200 old closed, 200 new |

Total snapshot rows: 14,111 + 200 + 200 = 14,511

### Expected dim_superhost_evolution variation

| Group | Count | status_change_count | Notes |
|-------|-------|-------------------|-------|
| Original superhosts, never mutated | ~1,720 | 0 | Were always superhost |
| Hosts flipped in phase 1, re-flipped in phase 2 | 100 | 2 | Back to original status |
| Hosts flipped in phase 1, stayed | 100 | 1 | Status changed once |
| New hosts flipped in phase 2 only | 100 | 1 | Status changed once |

"Ever been superhost" includes anyone who had `IS_SUPERHOST = 't'` in any snapshot layer.

All six output columns fully deterministic due to frozen `now()` and known UPDATED_AT values.

## Testing

### Solution seeds
- `snap__hosts` — full equality, exclude `dbt_scd_id` (non-deterministic hash)
- `dim_superhost_evolution` — full equality on all 6 columns

### Tests
- `AUTO_snap__hosts_existence.sql`
- `AUTO_snap__hosts_equality.sql` (exclude_columns: dbt_scd_id)
- `AUTO_dim_superhost_evolution_existence.sql`
- `AUTO_dim_superhost_evolution_equality.sql`

## Task Metadata

```yaml
task_id: airbnb010
status: ready
difficulty: hard
tags:
  - dbt
  - dbt-snapshots
  - scd2
  - model-creation
  - model-refactor
```

## Files to Create

```
tasks/airbnb010/
  task.yaml
  solution.sh
  setup.sh
  solutions/
    snap__hosts.sql              # snapshot definition (timestamp strategy)
    src_hosts.sql                # modified staging model (reads from snapshot)
    dim_superhost_evolution.sql  # analytical model
  seeds/
    solution__snap__hosts.csv
    solution__dim_superhost_evolution.csv
  tests/
    AUTO_snap__hosts_existence.sql
    AUTO_snap__hosts_equality.sql
    AUTO_dim_superhost_evolution_existence.sql
    AUTO_dim_superhost_evolution_equality.sql
  setup/
    watchdog.sh
    mutate_hosts.py
    deterministic_mutate.py
```
