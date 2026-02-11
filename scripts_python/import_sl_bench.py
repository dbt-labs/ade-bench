#!/usr/bin/env python3
"""
One-off converter: import dbt Semantic Layer LLM Benchmark challenges into ADE-Bench tasks.

Usage:
    uv run --with rdflib scripts_python/import_sl_bench.py \
        --ttl /path/to/acme-benchmark.ttl \
        --output tasks/ \
        --db-path shared/databases/duckdb/acme_insurance.duckdb
"""

import argparse
import csv
import io
import os
import re
import sys
import textwrap
from collections import defaultdict
from pathlib import Path

import yaml

try:
    import duckdb
except ImportError:
    print("ERROR: duckdb is required. Install with: pip install duckdb", file=sys.stderr)
    sys.exit(1)

try:
    from rdflib import Graph, Namespace, RDF
except ImportError:
    print("ERROR: rdflib is required. Run with: uv run --with rdflib scripts_python/import_sl_bench.py", file=sys.stderr)
    sys.exit(1)


QandA = Namespace("http://models.data.world/benchmarks/QandA#")
DWT = Namespace("https://templates.data.world/")
DCT = Namespace("http://purl.org/dc/terms/")


def parse_ttl(ttl_path: str) -> tuple[list[dict], list[dict]]:
    """Parse the .ttl file and return (inquiries, sql_queries)."""
    g = Graph()
    g.parse(ttl_path, format="turtle")

    # Extract SQL queries
    sql_queries = {}
    for subj in g.subjects(RDF.type, DWT.SqlQuery):
        query_text = str(g.value(subj, QandA.queryText, default=""))
        title = str(g.value(subj, DCT.title, default=""))
        description = str(g.value(subj, DCT.description, default=""))
        sql_queries[subj] = {
            "uri": str(subj),
            "query_text": query_text,
            "title": title,
            "description": description,
        }

    # Extract SPARQL queries (to identify and skip SPARQL-only expects)
    sparql_queries = set()
    for subj in g.subjects(RDF.type, DWT.SparqlQuery):
        sparql_queries.add(subj)

    # Extract Inquiries and link to SQL queries
    inquiries = []
    for subj in g.subjects(RDF.type, QandA.Inquiry):
        prompt = str(g.value(subj, QandA.prompt, default=""))
        expects = list(g.objects(subj, QandA.expects))

        # Find SQL expects (skip SPARQL)
        sql_expects = [e for e in expects if e in sql_queries]

        if not sql_expects:
            continue  # Skip inquiries that only have SPARQL expects

        for sql_uri in sql_expects:
            inquiries.append({
                "uri": str(subj),
                "prompt": prompt,
                "sql_query": sql_queries[sql_uri],
            })

    return inquiries, list(sql_queries.values())


def extract_category(title: str) -> str:
    """Extract HQLS/LQLS/HQHS/LQHS from the title."""
    match = re.match(r"(HQLS|LQLS|HQHS|LQHS)", title)
    if match:
        return match.group(1).lower()
    return "unknown"


def assess_difficulty(sql: str) -> str:
    """Heuristic difficulty assessment based on SQL complexity."""
    sql_upper = sql.upper()

    join_count = len(re.findall(r'\bJOIN\b', sql_upper))
    has_subquery = "SELECT" in sql_upper[sql_upper.find("FROM"):] if "FROM" in sql_upper else False
    has_group_by = "GROUP BY" in sql_upper
    has_avg = "AVG(" in sql_upper or "AVERAGE" in sql_upper
    has_complex_agg = any(fn in sql_upper for fn in ["SUM(", "AVG(", "DATEDIFF("])
    has_case = "CASE" in sql_upper
    has_window = "OVER(" in sql_upper or "OVER (" in sql_upper

    if join_count >= 4 or has_subquery or (has_complex_agg and join_count >= 3) or has_window or has_case:
        return "hard"
    elif join_count >= 2 or has_group_by or has_complex_agg:
        return "medium"
    else:
        return "easy"


def run_gold_query(db_path: str, sql: str) -> tuple[list[str], list[tuple]]:
    """Execute gold SQL against DuckDB and return (columns, rows)."""
    con = duckdb.connect(db_path, read_only=True)
    try:
        result = con.execute(sql)
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()
        return columns, rows
    finally:
        con.close()


def rows_to_csv(columns: list[str], rows: list[tuple]) -> str:
    """Convert query results to CSV string."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)
    for row in rows:
        writer.writerow(row)
    return output.getvalue()


def adapt_sql_for_duckdb(sql: str) -> str:
    """Adapt gold SQL queries for DuckDB compatibility."""
    # Fix DATE_DIFF with double-quoted "day" -> single-quoted 'day'
    # DuckDB datediff syntax: datediff('unit', start, end)
    sql = re.sub(
        r'DATE_DIFF\s*\(\s*(\w+)\s*,\s*(\w+)\s*,\s*"(\w+)"\s*\)',
        r"datediff('\3', \1, \2)",
        sql,
    )
    # Remove # line comments (MySQL-style) — replace with -- comments
    sql = re.sub(r'(?m)^(\s*)#(.*)$', r'\1--\2', sql)
    return sql


def generate_task(
    task_id: str,
    inquiry: dict,
    category: str,
    difficulty: str,
    output_dir: Path,
    db_path: str,
) -> bool:
    """Generate a single task directory. Returns True on success."""
    sql_query = inquiry["sql_query"]
    gold_sql_original = sql_query["query_text"]
    gold_sql = adapt_sql_for_duckdb(gold_sql_original)
    title = sql_query["title"]
    prompt_text = inquiry["prompt"]

    task_dir = output_dir / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    # Try running the gold SQL to generate solution seed
    try:
        columns, rows = run_gold_query(db_path, gold_sql)
    except Exception as e:
        print(f"  WARNING: Gold SQL failed for {task_id}: {e}")
        print(f"  SQL: {gold_sql[:200]}...")
        # Write a note file and continue — the task is still valid, just needs manual CSV
        (task_dir / "GOLD_SQL_ERROR.txt").write_text(f"Error: {e}\nSQL: {gold_sql}\n")
        columns, rows = [], []

    # Write solution seed CSV
    seeds_dir = task_dir / "seeds"
    seeds_dir.mkdir(exist_ok=True)
    if columns and rows:
        csv_content = rows_to_csv(columns, rows)
        (seeds_dir / "solution__result.csv").write_text(csv_content)
    elif columns:
        # Query returned 0 rows — still write header
        csv_content = rows_to_csv(columns, [])
        (seeds_dir / "solution__result.csv").write_text(csv_content)

    # Strip whitespace from prompt text to avoid YAML indentation issues
    prompt_text = prompt_text.strip()

    base_prompt = f"{prompt_text}\n\nWrite a model called result.sql containing your answer."
    sl_prompt = f"Using the dbt semantic layer, answer this question:\n\n{prompt_text}\n\nWrite a model called result.sql containing your answer."

    # Build task data as a dict and serialize with yaml.dump for correctness
    task_data = {
        "task_id": task_id,
        "status": "ready",
        "description": title,
        "prompts": [
            {"key": "base", "prompt": base_prompt},
            {"key": "with_sl", "prompt": sl_prompt},
        ],
        "author_name": "dbt-labs",
        "author_email": "noreply@getdbt.com",
        "difficulty": difficulty,
        "tags": [
            "semantic-layer",
            "metricflow",
            "free-text",
            "acme-insurance",
            category,
        ],
        "test_setup": "dbt run --select result",
        "solution_seeds": [{"table_name": "result"}],
        "variants": [
            {
                "db_type": "duckdb",
                "db_name": "acme_insurance",
                "project_type": "dbt",
                "project_name": "acme_insurance",
            }
        ],
    }
    task_yaml = yaml.dump(task_data, default_flow_style=False, sort_keys=False, allow_unicode=True)
    (task_dir / "task.yaml").write_text(task_yaml)

    # Write solution.sh
    solution_sh = f"""#!/bin/bash
cat > models/result.sql << 'GOLD_SQL'
{gold_sql}
GOLD_SQL

dbt run --select result
"""
    (task_dir / "solution.sh").write_text(solution_sh)
    os.chmod(task_dir / "solution.sh", 0o755)

    return True


def main():
    parser = argparse.ArgumentParser(description="Import dbt SL LLM benchmark into ADE-Bench tasks")
    parser.add_argument("--ttl", required=True, help="Path to acme-benchmark.ttl")
    parser.add_argument("--output", required=True, help="Output directory for tasks (e.g., tasks/)")
    parser.add_argument("--db-path", required=True, help="Path to acme_insurance.duckdb")
    parser.add_argument("--dry-run", action="store_true", help="Parse and report without generating files")
    args = parser.parse_args()

    output_dir = Path(args.output)

    print(f"Parsing TTL file: {args.ttl}")
    inquiries, all_sql = parse_ttl(args.ttl)
    print(f"Found {len(inquiries)} inquiries with SQL queries")
    print(f"Total SQL queries in file: {len(all_sql)}")

    # Deduplicate inquiries by (prompt, sql_query_text) to avoid duplicates
    seen = set()
    unique_inquiries = []
    for inq in inquiries:
        key = (inq["prompt"], inq["sql_query"]["query_text"])
        if key not in seen:
            seen.add(key)
            unique_inquiries.append(inq)
    print(f"Unique (prompt, SQL) pairs: {len(unique_inquiries)}")

    # Group by category
    by_category = defaultdict(list)
    for inq in unique_inquiries:
        cat = extract_category(inq["sql_query"]["title"])
        by_category[cat].append(inq)

    print("\nCategory breakdown:")
    for cat in sorted(by_category.keys()):
        print(f"  {cat.upper()}: {len(by_category[cat])} tasks")

    if args.dry_run:
        print("\n--- DRY RUN: Not generating files ---")
        for cat in sorted(by_category.keys()):
            for i, inq in enumerate(by_category[cat], 1):
                task_id = f"free_text_acme_{cat}_{i:03d}"
                difficulty = assess_difficulty(inq["sql_query"]["query_text"])
                print(f"  {task_id} [{difficulty}]: {inq['sql_query']['title']}")
                print(f"    Prompt: {inq['prompt'][:100]}...")
        return

    # Generate tasks
    all_task_ids = []
    for cat in sorted(by_category.keys()):
        for i, inq in enumerate(by_category[cat], 1):
            task_id = f"free_text_acme_{cat}_{i:03d}"
            difficulty = assess_difficulty(inq["sql_query"]["query_text"])
            print(f"Generating {task_id} [{difficulty}]...")
            success = generate_task(
                task_id=task_id,
                inquiry=inq,
                category=cat,
                difficulty=difficulty,
                output_dir=output_dir,
                db_path=args.db_path,
            )
            if success:
                all_task_ids.append(task_id)

    print(f"\nGenerated {len(all_task_ids)} tasks")

    # Print task IDs for experiment set
    print("\n--- Task IDs for experiment set ---")
    for tid in all_task_ids:
        print(f"  - {tid}")


if __name__ == "__main__":
    main()
