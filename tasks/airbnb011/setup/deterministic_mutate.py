"""Apply deterministic mutations for test_setup. Three phases:
Phase 1: Flip IS_SUPERHOST for first 200 hosts by ID
Phase 2: Re-flip first 100 of those + flip next 100 new (ranks 201-300)
Phase 3: INSERT 50 new hosts (25 superhost, 25 non-superhost) with duplicate names

UPDATED_AT is never modified — stays at 1980-01-01 throughout.
"""

import argparse
import duckdb

DB_PATH = "/app/airbnb.duckdb"


def get_ordered_host_ids(conn):
    """Get all host IDs ordered by ID where IS_SUPERHOST is not null."""
    return [
        r[0]
        for r in conn.execute(
            "SELECT ID FROM raw_hosts WHERE IS_SUPERHOST IS NOT NULL ORDER BY ID"
        ).fetchall()
    ]


def flip_hosts(conn, host_ids):
    """Flip IS_SUPERHOST for given host IDs. UPDATED_AT stays at 1980-01-01."""
    if not host_ids:
        return
    placeholders = ", ".join(["?"] * len(host_ids))
    conn.execute(
        f"""
        UPDATE raw_hosts
        SET IS_SUPERHOST = CASE WHEN IS_SUPERHOST = 't' THEN 'f' ELSE 't' END
        WHERE ID IN ({placeholders})
    """,
        host_ids,
    )
    print(f"Flipped {len(host_ids)} hosts (UPDATED_AT unchanged)")


def insert_new_hosts(conn):
    """Insert 50 new hosts: 25 superhosts and 25 non-superhosts.
    Names are copied from existing hosts to test unique_key handling."""
    max_id = conn.execute("SELECT MAX(ID) FROM raw_hosts").fetchone()[0]

    # Get 25 superhost names and 25 non-superhost names to duplicate
    super_names = [
        r[0]
        for r in conn.execute(
            "SELECT NAME FROM raw_hosts WHERE IS_SUPERHOST = 't' AND NAME IS NOT NULL ORDER BY ID LIMIT 25"
        ).fetchall()
    ]
    non_super_names = [
        r[0]
        for r in conn.execute(
            "SELECT NAME FROM raw_hosts WHERE IS_SUPERHOST = 'f' AND NAME IS NOT NULL ORDER BY ID LIMIT 25"
        ).fetchall()
    ]

    new_id = max_id + 1
    rows = []
    for name in super_names:
        rows.append((new_id, name, "t", "2024-09-01 00:00:00", "1980-01-01 00:00:00"))
        new_id += 1
    for name in non_super_names:
        rows.append((new_id, name, "f", "2024-09-01 00:00:00", "1980-01-01 00:00:00"))
        new_id += 1

    conn.executemany("INSERT INTO raw_hosts VALUES (?, ?, ?, ?::TIMESTAMP, ?::TIMESTAMP)", rows)
    print(f"Inserted {len(rows)} new hosts (IDs {max_id + 1} to {new_id - 1})")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", type=int, required=True, choices=[1, 2, 3])
    args = parser.parse_args()

    conn = duckdb.connect(DB_PATH)
    host_ids = get_ordered_host_ids(conn)

    if args.phase == 1:
        flip_hosts(conn, host_ids[:200])

    elif args.phase == 2:
        phase2_ids = host_ids[:100] + host_ids[200:300]
        flip_hosts(conn, phase2_ids)

    elif args.phase == 3:
        insert_new_hosts(conn)

    conn.close()


if __name__ == "__main__":
    main()
