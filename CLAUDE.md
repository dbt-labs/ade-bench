# CLAUDE.md - ADE-Bench Development Notes

## Project Overview
ADE-Bench (Analytics and Data Engineering Benchmark) is a benchmarking framework for evaluating AI agents on data analyst tasks. It's modeled after terminal-bench but specialized for dbt and SQL workflows.

## Key Differences from Terminal-Bench
1. **Containers**: Include dbt + database (DuckDB/SQLite/PostgreSQL) instead of general dev environments
2. **Tests**: SQL queries validate results instead of pytest
3. **Tasks**: Focus on data transformations, aggregations, and analytics

## Architecture

### Core Components
- `harness.py`: Main orchestrator for running benchmarks
- `trial_handler.py`: Manages individual task execution
- `sql_parser.py`: Validates task results using SQL queries
- `docker_compose_manager.py`: Handles dbt/database containers

### Directory Structure
```
ade-bench/
├── ade_bench/          # Core Python package
├── tasks/              # Individual task definitions
├── docker/base/        # Base Docker images
├── shared/defaults/    # Default configurations
├── experiments/        # Benchmark results
└── datasets/           # Dataset configurations
```

### Task Structure
Each task contains:
- `task.yaml`: Metadata and configuration
- `dbt_project/`: dbt project files
- `tests/`: SQL validation queries
- `expected/`: Expected query results
- `solution.sh`: Reference solution
- `Dockerfile`: Container setup (optional, uses defaults)

## Running Commands

### Create a new task:
```bash
uv run wizard
```

### Run benchmarks:
```bash
# With sage agent
uv run scripts_python/run_harness.py --agent sage --task-ids task1 task2
```

### Key Parameters:
- `--agent`: Agent type (sage, claude, codex, gemini, etc.)
- `--model`: LLM model for AI agents
- `--dataset-config`: YAML file defining task collection
- `--n-concurrent-trials`: Parallel execution (default: 4)
- `--no-rebuild`: Skip Docker rebuilds
- `--cleanup`: Remove Docker resources after run
- `--plugin-set`: Plugin set names from `experiment_sets/plugin-sets.yaml` (space-separated). Controls skills, MCP servers, and allowed tools. Defaults to `none` (no plugins).

## Development Workflow

1. **Creating Tasks**:
   - Use `uv run wizard` or manually create structure
   - Add seed data to `data/`
   - Write dbt models in `dbt_project/models/`
   - Create SQL tests in `tests/`
   - Define expected results in `expected/`

2. **Testing**:
   - Run with sage agent first to validate task
   - Check logs in `experiments/[run_id]/`
   - Verify SQL test results

3. **Adding Agents**:
   - Extend `BaseAgent` class
   - Register in `AgentFactory`
   - Implement `run()` method

## Git Worktrees

This project supports git worktrees for parallel development:

```bash
git worktree add .worktrees/feature-name -b feature/feature-name
```

**Database files:** Large database files (`.duckdb`, `.parquet`) are gitignored and only exist in the main repository at `shared/databases/`. The code automatically resolves these from the main repo even when running in a worktree.

**Other shared resources:** Config files (`shared/config/`), scripts (`shared/scripts/`), migrations (`shared/migrations/`), and projects (`shared/projects/`) are worktree-aware and can be modified per worktree.

## Docker Setup

Base images provided:
- `Dockerfile.duckdb-dbt`: For DuckDB-based tasks
- `Dockerfile.snowflake-dbt`: For Snowflake-based tasks
- `Dockerfile.snowflake-dbtf`: For Snowflake-based tasks

Default docker-compose files handle:
- Container networking
- Health checks (for PostgreSQL)
- Volume mounting for dbt projects and data

Database support:
- **DuckDB**: File-based, great for analytical workloads
- **SQLite**: File-based, lightweight and simple
- **PostgreSQL**: Server-based, full-featured RDBMS
- **Snowflake**: Cloud-based data warehouse with dbt integration

## Shared Database System

Tasks can now use shared databases to avoid duplicating large datasets:

### Directory Structure
```
shared/databases/
├── duckdb/       # DuckDB database files
├── sqlite/       # SQLite database files
├── postgres/     # PostgreSQL initialization scripts
├── snowflake/    # Snowflake initialization scripts
└── catalog.yaml  # Database metadata
```

### Using Shared Databases in Tasks

In `task.yaml`:
```yaml
database:
  source: shared          # Use shared database
  name: shopify          # Database name (without extension)
  type: duckdb          # Database type
```

For local databases (default behavior):
```yaml
database:
  source: local  # Or omit database config entirely
  path: data/   # Local data directory
```

**Note**: Shared databases are always copied into containers to prevent corruption. The original shared database files are never modified by tasks.

### Managing Shared Databases

```python
from ade_bench.database import DatabasePoolManager

# Initialize manager
pool = DatabasePoolManager()

# Register a new database
pool.register_database(
    db_path=Path("my_data.duckdb"),
    description="E-commerce dataset",
    tables=["orders", "products", "customers"]
)

# List available databases
for db in pool.list_databases():
    print(f"{db.name} ({db.type.value}): {db.description}")
```

## Next Steps for Implementation

1. **Create example tasks** demonstrating:
   - Basic aggregations
   - Window functions
   - CTEs and complex transformations
   - dbt tests and documentation

2. **Implement AI agents**:
   - Port terminus agent from terminal-bench
   - Add support for Claude, GPT-4, etc.

3. **Enhance testing**:
   - Support for comparing DataFrames
   - Tolerance for floating-point comparisons
   - Performance benchmarks

4. **Add features**:
   - S3 upload for results
   - Database storage for tracking
   - Visualization dashboard
