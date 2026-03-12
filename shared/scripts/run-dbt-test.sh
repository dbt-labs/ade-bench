#! /bin/bash

export DBT_STATIC_ANALYSIS=off
export DBT_PARTIAL_PARSE=False

# STEP 1: Run the test setup script if it exists
if [ -f "/scripts/test-setup.sh" ]; then
    bash /scripts/test-setup.sh
fi

# STEP 2: Remove any existing singular tests and add solution test directory
rm -rf tests
mkdir tests

# STEP 3: Parse arguments to filter for tests
for arg in "$@"; do
    case $arg in
        --db-type=*) db_type="${arg#*=}" ;;
        --project-type=*) project_type="${arg#*=}" ;;
    esac
done

echo "Filtering for db_type='$db_type', project_type='$project_type'"

# STEP 4: Copy files with filtering
included_count=0
for file in /tests/*; do
    [[ -f "$file" ]] || continue

    # Non-SQL files: always include
    if [[ ! "$file" =~ \.sql$ ]]; then
        cp "$file" tests/
        continue
    fi

    # SQL files: apply filtering
    include=true

    # Check db specification
    if [[ -n "$db_type" ]] && grep -q "^-- *db:" "$file"; then
        if ! grep -q "^-- *db:.*$db_type" "$file"; then
            include=false
        fi
    fi

    # Check project-type specification
    if [[ -n "$project_type" ]] && grep -q "^-- *project-type:" "$file"; then
        if ! grep -q "^-- *project-type:.*$project_type" "$file"; then
            include=false
        fi
    fi

    if [[ "$include" == true ]]; then
        echo "Including: $(basename "$file")"
        cp "$file" tests/
        ((included_count++))
    else
        echo "Excluding: $(basename "$file")"
    fi
done

echo "[ade-bench] expected_test_count=$included_count"

# STEP 5: Setup seed directlry and run dbt seed
if [ -d "/seeds" ]; then
    mkdir -p seeds
    cp /seeds/* seeds/

    bash /scripts/seed-schema.sh

    dbt seed
fi

# run dbt data tests for evaluation
dbt test --select "test_type:singular"