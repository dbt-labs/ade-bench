#!/bin/bash
# shared/scripts/run-comparison.sh
# Orchestrate table comparison for failing equality tests.
# Runs inside the container after dbt test. All output goes to stdout
# so it appears in post-agent logs.
#
# NOTE: No `set -e` — this runs after test failures, commands may return
# non-zero. We handle errors explicitly.
#
# Usage: bash /scripts/run-comparison.sh --db-type=duckdb

for arg in "$@"; do
    case $arg in
        --db-type=*) db_type="${arg#*=}" ;;
    esac
done

# Auto-detect DuckDB path from well-known container location
if [ "$db_type" = "duckdb" ]; then
    db_path=$(ls /app/*.duckdb 2>/dev/null | head -1)
    if [ -z "$db_path" ]; then
        echo "[ade-bench] Warning: no .duckdb file found at /app/, skipping comparison"
        exit 0
    fi
fi

FAILING_JSON="/tmp/failing_pairs.json"
DATA_COMPARISONS_DIR="/app/data_comparisons"

# Step 1: Detect failing equality tests from run_results.json + manifest.json
echo "[ade-bench] Checking for failing equality tests..."
python3 /scripts/detect_failing_equality_tests.py \
    --run-results target/run_results.json \
    --manifest target/manifest.json \
    --output "$FAILING_JSON"

PAIR_COUNT=$(python3 -c "import json, sys; print(len(json.load(open(sys.argv[1]))))" "$FAILING_JSON" 2>/dev/null || echo "0")
if [ "$PAIR_COUNT" = "0" ]; then
    exit 0
fi

# Step 2: Dump all referenced tables
mkdir -p "$DATA_COMPARISONS_DIR"

# Write relation names to a temp file (one per line) to avoid shell quoting issues
RELATIONS_FILE="/tmp/comparison_relations.txt"
python3 -c "
import json, sys
pairs = json.load(open(sys.argv[1]))
relations = set()
for p in pairs:
    relations.add(p['actual'])
    relations.add(p['expected'])
for r in sorted(relations):
    print(r)
" "$FAILING_JSON" > "$RELATIONS_FILE"

ALL_RELATIONS=$(tr '\n' ' ' < "$RELATIONS_FILE")
echo "[ade-bench] Dumping tables: $ALL_RELATIONS"

DUMP_ARGS="--relations $ALL_RELATIONS --output $DATA_COMPARISONS_DIR/tables"
if [ "$db_type" = "duckdb" ]; then
    DUMP_ARGS="$DUMP_ARGS --db-type duckdb --db-path $db_path"
elif [ "$db_type" = "snowflake" ]; then
    DUMP_ARGS="$DUMP_ARGS --db-type snowflake"
fi

python3 /scripts/dump_tables.py $DUMP_ARGS

# Step 3: Compare each pair and produce diff HTML
python3 -c "
import json, subprocess, os, shutil

pairs = json.loads(open('$FAILING_JSON').read())
for p in pairs:
    model = p['model_name']
    actual_path = '$DATA_COMPARISONS_DIR/tables/' + p['actual'] + '.parquet'
    expected_path = '$DATA_COMPARISONS_DIR/tables/' + p['expected'] + '.parquet'
    output_dir = '$DATA_COMPARISONS_DIR/' + model

    os.makedirs(output_dir, exist_ok=True)

    # Copy parquet and csv files into per-model directory
    for ext in ['parquet', 'csv']:
        for src_name, dst_name in [(p['actual'], 'actual'), (p['expected'], 'expected')]:
            src = '$DATA_COMPARISONS_DIR/tables/' + src_name + '.' + ext
            dst = output_dir + '/' + dst_name + '.' + ext
            if os.path.exists(src):
                shutil.copy2(src, dst)

    # Run comparison
    subprocess.run([
        'python3', '/scripts/compare_tables.py',
        '--expected', expected_path,
        '--actual', actual_path,
        '--expected-name', p['expected'],
        '--actual-name', p['actual'],
        '--model-name', model,
        '--output', output_dir + '/diff.html',
    ])
"

echo "[ade-bench] Comparison artifacts written to $DATA_COMPARISONS_DIR"
