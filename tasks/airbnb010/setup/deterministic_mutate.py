"""Apply deterministic mutations for test_setup. Two phases:
Phase 1: Flip first 200 hosts by ID, set UPDATED_AT = '2024-06-01'
Phase 2: Re-flip first 100 of those + flip next 100 new, set UPDATED_AT = '2025-01-01'
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


def flip_hosts(conn, host_ids, updated_at):
    """Flip IS_SUPERHOST for given host IDs and set UPDATED_AT."""
    if not host_ids:
        return
    placeholders = ", ".join(["?"] * len(host_ids))
    conn.execute(
        f"""
        UPDATE raw_hosts
        SET IS_SUPERHOST = CASE WHEN IS_SUPERHOST = 't' THEN 'f' ELSE 't' END,
            UPDATED_AT = TIMESTAMP '{updated_at}'
        WHERE ID IN ({placeholders})
    """,
        host_ids,
    )
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
