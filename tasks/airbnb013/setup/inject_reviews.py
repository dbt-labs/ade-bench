#!/usr/bin/env python3
"""
Appends 5 fixed new reviews (from new_reviews.csv) to raw_reviews.
Idempotent: deletes matching (listing_id, date, reviewer_name) rows before inserting.
"""

import csv
import os
import duckdb

DB_PATH = "/app/airbnb.duckdb"
CSV_PATH = os.path.join(os.path.dirname(__file__), "new_reviews.csv")

conn = duckdb.connect(DB_PATH)

with open(CSV_PATH) as f:
    rows = list(csv.DictReader(f))

for row in rows:
    conn.execute(
        "DELETE FROM raw_reviews WHERE listing_id=? AND date=? AND reviewer_name=?",
        [int(row["listing_id"]), row["date"], row["reviewer_name"]],
    )

for row in rows:
    conn.execute(
        "INSERT INTO raw_reviews (listing_id, date, reviewer_name, comments, sentiment) VALUES (?, ?, ?, ?, ?)",
        [
            int(row["listing_id"]),
            row["date"],
            row["reviewer_name"],
            row["comments"],
            row["sentiment"],
        ],
    )

print(f"Injected {len(rows)} reviews on {rows[0]['date']}.")
conn.close()
