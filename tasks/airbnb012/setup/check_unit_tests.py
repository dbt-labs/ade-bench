#!/usr/bin/env python3
"""
Parses the dbt manifest to find unit tests for NPS models.
Writes results to the unit_test_manifest table in DuckDB.
Run in test_setup before singular tests execute.
"""

import json
import os
import subprocess
import csv
import duckdb

PROJECT_DIR = "/app"
MANIFEST_PATH = os.path.join(PROJECT_DIR, "target", "manifest.json")
SEED_PATH = os.path.join(PROJECT_DIR, "seeds", "unit_test_manifest.csv")
DB_PATH = "/app/airbnb.duckdb"

TARGET_MODELS = {"listing_agg_nps_reviews", "daily_agg_nps_reviews"}

# Run dbt parse to generate fresh manifest
result = subprocess.run(["dbt", "parse"], cwd=PROJECT_DIR, capture_output=True, text=True)
if result.returncode != 0:
    print("WARNING: dbt parse failed. Writing empty manifest.")
    print(result.stderr)

# Read manifest (may not exist if parse failed)
unit_tests = []
if os.path.exists(MANIFEST_PATH):
    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)

    for node_key, node in manifest.get("unit_tests", {}).items():
        model_short = node.get("model", "")
        if model_short in TARGET_MODELS:
            unit_tests.append(
                {
                    "model_name": model_short,
                    "test_name": node.get("name", ""),
                }
            )

# Write seed CSV (used as backup; primary storage is DuckDB)
os.makedirs(os.path.dirname(SEED_PATH), exist_ok=True)
with open(SEED_PATH, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["model_name", "test_name"])
    writer.writeheader()
    writer.writerows(unit_tests)

print(f"Found {len(unit_tests)} unit tests for NPS models: {unit_tests}")

# Write directly to DuckDB so the singular SQL test can query it
conn = duckdb.connect(DB_PATH)
conn.execute("DROP TABLE IF EXISTS main.unit_test_manifest")
if unit_tests:
    conn.execute(
        """
        CREATE TABLE main.unit_test_manifest AS
        SELECT model_name, test_name
        FROM read_csv_auto(?)
    """,
        [SEED_PATH],
    )
else:
    conn.execute("""
        CREATE TABLE main.unit_test_manifest (
            model_name VARCHAR,
            test_name  VARCHAR
        )
    """)
conn.close()

print("unit_test_manifest table written to DuckDB.")
