#!/usr/bin/env python3
"""
Runs agent's unit tests against each broken NPS model variant.
For each variant: swaps model file, runs dbt test --select {model},test_type:unit,
records caught_bug=True if any test FAILED (good), False if all passed (bad).
Writes one row per variant to broken_model_results table in DuckDB.
"""
import os
import shutil
import subprocess
import duckdb

DB_PATH = "/app/airbnb.duckdb"
PROJECT_DIR = "/app"
BROKEN_DIR = "/tmp/broken"
MODELS_AGG_DIR = os.path.join(PROJECT_DIR, "models", "agg")

broken_variants = [
    # listing_agg_nps_reviews variants
    {"variant_id": "listing_reversed_sign",        "model": "listing_agg_nps_reviews", "broken_file": "listing_reversed_sign.sql"},
    {"variant_id": "listing_missing_negative",     "model": "listing_agg_nps_reviews", "broken_file": "listing_missing_negative.sql"},
    {"variant_id": "listing_neutral_in_numerator", "model": "listing_agg_nps_reviews", "broken_file": "listing_neutral_in_numerator.sql"},
    {"variant_id": "listing_wrong_denominator",    "model": "listing_agg_nps_reviews", "broken_file": "listing_wrong_denominator.sql"},
    # daily_agg_nps_reviews variants
    {"variant_id": "daily_reversed_sign",          "model": "daily_agg_nps_reviews",   "broken_file": "daily_reversed_sign.sql"},
    {"variant_id": "daily_neutral_in_numerator",   "model": "daily_agg_nps_reviews",   "broken_file": "daily_neutral_in_numerator.sql"},
    {"variant_id": "daily_wrong_window",           "model": "daily_agg_nps_reviews",   "broken_file": "daily_wrong_window.sql"},
]

results = []

for v in broken_variants:
    variant_id = v["variant_id"]
    model = v["model"]
    original_file = os.path.join(MODELS_AGG_DIR, f"{model}.sql")
    broken_file = os.path.join(BROKEN_DIR, v["broken_file"])
    backup = original_file + ".bak"

    shutil.copy2(original_file, backup)
    shutil.copy2(broken_file, original_file)

    try:
        result = subprocess.run(
            ["dbt", "test", "--select", f"{model},test_type:unit"],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
        )
        # Exit code != 0: at least one test FAILED → bug was caught (good)
        # "Nothing to do": no unit tests defined → not caught
        no_tests = "Nothing to do" in result.stdout or "no tests" in result.stdout.lower()
        caught_bug = result.returncode != 0 and not no_tests
        print(f"[{variant_id}] caught_bug={caught_bug} (returncode={result.returncode})")
        if not caught_bug:
            print(f"  WARNING: unit tests did NOT catch bug in '{variant_id}'")
            print(result.stdout[-2000:])
    except Exception as e:
        print(f"[{variant_id}] error: {e}")
        caught_bug = False
    finally:
        shutil.copy2(backup, original_file)
        os.remove(backup)

    results.append({"variant_id": variant_id, "model_name": model, "caught_bug": caught_bug})

conn = duckdb.connect(DB_PATH)
conn.execute("DROP TABLE IF EXISTS main.broken_model_results")
conn.execute("""
    CREATE TABLE main.broken_model_results (
        variant_id VARCHAR,
        model_name VARCHAR,
        caught_bug BOOLEAN
    )
""")
for r in results:
    conn.execute(
        "INSERT INTO main.broken_model_results VALUES (?, ?, ?)",
        [r["variant_id"], r["model_name"], r["caught_bug"]]
    )
conn.close()

print(f"broken_model_results written: {results}")
