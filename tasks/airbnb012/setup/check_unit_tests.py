#!/usr/bin/env python3
import json
import os
import subprocess
import csv

PROJECT_DIR = "/app"
MANIFEST_PATH = os.path.join(PROJECT_DIR, "target", "manifest.json")
SEED_PATH = os.path.join(PROJECT_DIR, "seeds", "unit_test_manifest.csv")

TARGET_MODELS = {"listing_agg_nps_reviews", "daily_agg_nps_reviews"}

result = subprocess.run(["dbt", "parse"], cwd=PROJECT_DIR, capture_output=True, text=True)
if result.returncode != 0:
    print("WARNING: dbt parse failed. Writing empty manifest.")
    print(result.stderr)

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

os.makedirs(os.path.dirname(SEED_PATH), exist_ok=True)
with open(SEED_PATH, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["model_name", "test_name"])
    writer.writeheader()
    writer.writerows(unit_tests)

print(f"Found {len(unit_tests)} unit tests for NPS models: {unit_tests}")
