#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import csv

PROJECT_DIR = "/app"
BROKEN_DIR = "/tmp/broken"
MODELS_AGG_DIR = os.path.join(PROJECT_DIR, "models", "agg")
MANIFEST_PATH = os.path.join(PROJECT_DIR, "target", "manifest.json")
SEED_PATH = os.path.join(PROJECT_DIR, "seeds", "broken_model_results.csv")

broken_variants = [
    # listing_agg_nps_reviews variants
    {
        "variant_id": "listing_reversed_sign",
        "model": "listing_agg_nps_reviews",
        "broken_file": "listing_reversed_sign.sql",
    },
    {
        "variant_id": "listing_missing_negative",
        "model": "listing_agg_nps_reviews",
        "broken_file": "listing_missing_negative.sql",
    },
    {
        "variant_id": "listing_neutral_in_numerator",
        "model": "listing_agg_nps_reviews",
        "broken_file": "listing_neutral_in_numerator.sql",
    },
    {
        "variant_id": "listing_wrong_denominator",
        "model": "listing_agg_nps_reviews",
        "broken_file": "listing_wrong_denominator.sql",
    },
    # daily_agg_nps_reviews variants
    {
        "variant_id": "daily_reversed_sign",
        "model": "daily_agg_nps_reviews",
        "broken_file": "daily_reversed_sign.sql",
    },
    {
        "variant_id": "daily_neutral_in_numerator",
        "model": "daily_agg_nps_reviews",
        "broken_file": "daily_neutral_in_numerator.sql",
    },
    {
        "variant_id": "daily_wrong_window",
        "model": "daily_agg_nps_reviews",
        "broken_file": "daily_wrong_window.sql",
    },
]

models_with_tests = set()
if os.path.exists(MANIFEST_PATH):
    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)
    for node_key, node in manifest.get("unit_tests", {}).items():
        models_with_tests.add(node.get("model", ""))

results = []

for v in broken_variants:
    variant_id = v["variant_id"]
    model = v["model"]
    original_file = os.path.join(MODELS_AGG_DIR, f"{model}.sql")
    broken_file = os.path.join(BROKEN_DIR, v["broken_file"])
    backup = original_file + ".bak"

    if model not in models_with_tests:
        print(f"[{variant_id}] no unit tests defined for {model}")
        results.append({"variant_id": variant_id, "model_name": model, "caught_bug": False})
        continue

    shutil.copy2(original_file, backup)
    shutil.copy2(broken_file, original_file)

    try:
        result = subprocess.run(
            ["dbt", "test", "--select", f"{model},test_type:unit"],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
        )
        caught_bug = result.returncode != 0
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

os.makedirs(os.path.dirname(SEED_PATH), exist_ok=True)
with open(SEED_PATH, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["variant_id", "model_name", "caught_bug"])
    writer.writeheader()
    writer.writerows(results)

print(f"broken_model_results written: {results}")
