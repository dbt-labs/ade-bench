#!/usr/bin/env python3
"""
Injects 5 extra reviews on the current max review date into raw_reviews.
Idempotent: removes previously injected rows before inserting.
Uses real data for realism and a fixed seed for determinism.
"""
import duckdb
import random

DB_PATH = "/app/airbnb.duckdb"
INJECT_MARKER = "[ade_bench_injected]"
INJECT_COUNT = 5

conn = duckdb.connect(DB_PATH)

# Idempotent: remove any previously injected rows
conn.execute(f"DELETE FROM raw_reviews WHERE comments LIKE '%{INJECT_MARKER}%'")

# Find the current max review date
max_date = conn.execute("SELECT MAX(date) FROM raw_reviews").fetchone()[0]
print(f"Max review date: {max_date}")

# Sample real reviewer names, listing IDs, and sentiments
real_reviewers = conn.execute("SELECT reviewer_name FROM raw_reviews ORDER BY reviewer_name").fetchall()
real_listings = conn.execute("SELECT DISTINCT listing_id FROM raw_reviews WHERE date = ? ORDER BY listing_id", [max_date]).fetchall()
real_sentiments = conn.execute("SELECT sentiment FROM raw_reviews ORDER BY sentiment").fetchall()

random.seed(42)
selected_reviewers = [r[0] for r in random.sample(real_reviewers, INJECT_COUNT)]
selected_listings = [r[0] for r in random.choices(real_listings, k=INJECT_COUNT)]
selected_sentiments = [r[0] for r in random.choices(real_sentiments, k=INJECT_COUNT)]

for i in range(INJECT_COUNT):
    conn.execute("""
        INSERT INTO raw_reviews (listing_id, date, reviewer_name, comments, sentiment)
        VALUES (?, ?, ?, ?, ?)
    """, [
        selected_listings[i],
        max_date,
        selected_reviewers[i],
        f"Great stay overall. {INJECT_MARKER}_{i}",
        selected_sentiments[i],
    ])

injected = conn.execute(f"SELECT COUNT(*) FROM raw_reviews WHERE comments LIKE '%{INJECT_MARKER}%'").fetchone()[0]
print(f"Injection complete. {injected} injected reviews in raw_reviews.")
conn.close()
