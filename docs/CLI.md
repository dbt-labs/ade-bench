# ADE-bench CLI

## Commands

To see a list of commands, run:

```bash
ade --help
```

### Run tasks

Run ADE-bench tasks with specific configurations:

```bash
# Run a specific task
ade run foo001 --db duckdb --project-type dbt --agent sage

# Run a specific task with a specific variant
ade run foo001.hard --db duckdb --project-type dbt --agent sage

# Run multiple tasks
ade run foo001 bar001 --db duckdb --project-type dbt --agent sage

# Run all ready tasks
ade run all --db duckdb --project-type dbt --agent sage

# Run an experiment set
ade run @my_experiment_set --db duckdb --project-type dbt --agent sage

# Run wildcard patterns
ade run foo+ bar+ --db duckdb --project-type dbt --agent sage

# Schedule tasks longest-first using runtime data from a previous run
ade run all --db duckdb --project-type dbt --agent sage \
  --duration-hints experiments/claude-haiku-4-5-20251001-latest
```

The `--duration-hints` option points to an experiment directory containing a `results.json`. Tasks are sorted by descending `runtime_ms` so the slowest tasks start first, reducing total wall-clock time when running with multiple concurrent trials. Tasks without a hint are assumed slow and scheduled first.

### View Results

View the results of your benchmark runs:

```bash
# Open the most recent run results in your browser
ade view

# List recent runs
ade view runs

# View a specific run
ade view run 2025-10-07__11-45-04

# List all available tasks with their prompts
ade view tasks

# Copy task details as TSV to clipboard
ade view tasks --copy
```

### Interactive Mode

Launch an interactive shell into a task environment:

```bash
# Launch an interactive shell into a task
ade interact --task-id foo001 --db duckdb --project-type dbt

# Include solution and test files in the interactive environment
ade interact --task-id foo001 --db duckdb --project-type dbt --include-all

# Set up a specific agent for testing (in a tmux session)
ade interact --task-id foo001 --db duckdb --project-type dbt --agent claude

# Run the agent on a task and then drop into interactive mode
ade interact --task-id foo001 --db duckdb --project-type dbt --agent claude --step post-agent

# Run the agent, evaluate the results, and then drop into interactive mode
ade interact --task-id foo001 --db duckdb --project-type dbt --agent claude --step post-eval

# Specify a run ID for the output directory
ade interact --task-id foo001 --db duckdb --project-type dbt --run-id debug-session
```

### Save Results

When using ADE-bench, you may create several test runs, and then larger runs you want to save as production runs. Use the commands below to copy runs in `experiments` directory into a new directory. By default, they will be `experiments_saved` directory, though you can choose a different one.

```bash
# Save the most recent run
ade save

# Save a specific run
ade save run 2025-10-07__11-45-04

# Save the most recent run to a specific directory
ade save --output-path experiments_saved_my_fun_project
```

### Database Migration

Migrate DuckDB databases to Snowflake:

```bash
# Migrate all DuckDB databases to Snowflake
ade migrate duckdb-to-snowflake

# Migrate specific databases only
ade migrate duckdb-to-snowflake --include foo bar

# Exclude specific databases
ade migrate duckdb-to-snowflake --exclude foo

# Use database export for better performance
ade migrate duckdb-to-snowflake --use-database-export
```