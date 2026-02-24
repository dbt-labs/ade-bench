# Contributing

Contributions to the ADE-bench project are welcome. All contributions are equally loved and appreciated—but contributions of new tests, either from new data sources or on top of existing ones, are loved more.

Most tests require three major components:

- A dbt project. This the environment that the agent will work in.
- Data. This is set of tables that the dbt project runs against. It can be an anonymized sample of data, but tests need data of some kind to be effective.
- A question to ask the agent, and an answer key to evaluate their work.

This document describes some of the technical details that are useful for contributing tasks. For an overview of how ADE-bench works, see the [README](/README.md).

---

## Contributing new tasks

Tasks are individual tests that are given to agents to solve. Tests have several major components:

- A source dbt project (see [Contributing new dbt projects](#contributing-new-dbt-projects))
- A source database (see [Contributing new data](#contributing-new-data))
- A question to ask the agent
- An optional setup script
- A solution script, which describes how to solve the task
- dbt tests, which are used to evaluate the agent's work
- Optional solution CSVs, which can be used to compare the agent's work to a known answer

### Setup and solution scripts

Setup scripts are used to modify the environment before the agent runs. They can be used to modify the dbt project, the database, or the agent's prompt. A simple setup script might look like this:

```bash
# Update dbt deps and run dbt
dbt deps
dbt run
```

Setup scripts can also be used to modify the database or dbt project. For example, see (analytics_engineering002)[/tasks/analytics_engineering002/setup.sh] for an example of a setup script that removes a comma from a dbt model.

Solution scripts are the answer key for the task. They should make whatever changes to the project or database that the agent would make if it solves the task correctly. When a task is run with an real agent (e.g., `ade run ... --agent claude`), the solution script will be ignored and won't be provided to the agent. When a task is run with the sage agent (e.g., `ade run ... --agent sage`), it will run the solution script.

#### Configuring different environments

When the `setup.sh` and `solution.sh` scripts run, ADE-bench passes the corresponding database and project type into the script as an argument. So if different updates are needed depending on the database or project type, these can be configured following patterns like the example below:

```bash
## This updates the schema config in the solution files, and then moves the files to the appropriate place

# Assign the solutions directory
SOLUTIONS_DIR="$(dirname "$(readlink -f "${BASH_SOURCE}")")/solutions"

# Assign the 'replace' value based on the database type
if [[ "$*" == *"--db-type=duckdb"* ]]; then
    replace='schema="main"'
else
    replace='schema="public"'
fi

# Loop over the files, update the value in the file, and move them
# from the solutions directory in the project directory
files=(
    "foo.sql"
    "bar.sql"
)

for file in "${files[@]}"; do
    find='schema="main"'
    sed -i "s/${find}/${replace}/g" $SOLUTIONS_DIR/$file
    cp $SOLUTIONS_DIR/$file models/$file
done
```

#### Running arbitrary SQL queries

ADE-bench provides a utility script (`run_sql.sh`) that allows you to run arbitrary SQL queries against the database from within `setup.sh` or `solution.sh` scripts. This can be useful when you need to modify the database schema or data directly.

**Usage:**

```bash
# In setup.sh or solution.sh, you can use run_sql.sh like this:
/scripts/run_sql.sh "$@" << SQL
-- Your SQL queries here
CREATE OR REPLACE TABLE foo_temp AS
  SELECT * REPLACE revenue * 10 as revenue
  FROM foo;

DROP TABLE foo;
ALTER TABLE foo_temp RENAME TO foo;
SQL
```

The script automatically:

- Extracts `--db-type` and `--project-type` from the arguments passed to your script
- Reads database connection details from `/app/profiles.yml`
- Detects the correct profile name based on the project and database type
- Executes the SQL against the appropriate database (DuckDB or Snowflake)
- Handles multiple SQL statements separated by semicolons

**Note:** In some instances, the text of the query may need to be modified depending on the database; you can use the if statements just above (i.e., `if [[ "$*" == *"--db-type=duckdb"* ]]...`) to modify the query based on the database type.

### dbt tests

For an overview of how dbt tests are used to evaulate trials, see the [README](README.md#how-trials-are-evaluated). This section describes advanced ways to configure tests.

#### Configuring different environments

Tests can be designated for specific environments using comment headers:

```sql
-- db: duckdb          # Only runs for DuckDB
-- db: snowflake duckdb # Runs for both Snowflake and DuckDB
-- project-type: dbt   # Only runs for dbt projects
```

Tests without an environment specification run on all environments.

#### Approximate equality tests

Sometimes databases give slightly different results. (For reasons, `select round(23/40,2)` is 0.58 in Snowflake, and 0.57 in DuckDB. Computers, man.) Or, the agent could write a query that returns a number rounded to a different number of decimals, and you want to be tolerant to that. Though there currently isn't a way to automatically create a test like this, `airbnb007` includes examples of `_with_tolerance` tests. This test will:

- Compare the number of rows, expected an exact match
- Compare the min and max values of date columns, expecting an exact match
- Compare the sum and averages of numeric columns, expecting the test table to be within a specified percentage band.

The "configuration" of that test is defined in a block at the top of the test:

```sql
-- Add the table name and the solution CSV
{% set test_and_solution_tables = ['daily_agg_nps_reviews','solution__daily_agg_nps_reviews'] %}

-- List date columns
{% set date_cols = ['review_date'] %}
-- List numeric columns and the tolerances. These are percentages, so sum_tolerance of 0.01 means
-- that the sum of each numeric column needs to be between 98% and 102% of the sums of the
-- corresponding column in the solution table.
{% set numeric_cols = ['nps_daily', 'reviews_daily', 'nps_28d', 'reviews_28d'] %}
{% set sum_tolerance = 0.02 %}
{% set avg_tolerance = 0.02 %}
```

### Solution seeds

Many tasks have `solution_seeds` defined in their `task.yaml` file. These are tables that are used to evalute an agent's work. For example, if you want an agent to create a `customers` table, you can add a CSV of that table in the `/seeds` directory called `solution__customers.csv`, and ADE-bench will compare that table to the agent's table.

By default, these seeds must perfectly match the agent-produced table, but you can also:

- specify a [subset of columns](https://github.com/dbt-labs/dbt-utils#equality-source) to include or exclude from the table equality comparison
- disable the automatic generation of either the equality or existence test.
- specify alternate solution seeds for tasks that have multiple valid answers.

```yaml
solution_seeds:
  - table_name: customers
    alternates:
    - customers_alt_1
    - customers_alt_2
    exclude_columns:
    - created_at
```

In the example above, the agent would be expected to create a table called `customers` (and just that table), and for that table to match one of the three seeds (`solution__customers.csv`, `solution__customers_alt_1.csv`, and `solution__customers_alt_2.csv`). All the comparisons would ignore the `created_at` column.

#### Automatically producing solution seeds

Instead of making a solution seed CSVs by hand, ADE-bench can output seed files based on the results of the `sage` agent:

```bash
ade run my_new_task --db duckdb --agent sage --project-type dbt --seed
```

After ADE-bench finishes running the trial, it generates the following files in the task's `seeds` directory:

- One CSV file called `solution__[table_name].csv` for each table defined in the `solution_seeds` key of task.yaml
- One schema file called `_no-op.txt` for the whole task. This is a utility file that is used when tables are uploaded to ensure schemas are created with the correct data types. (Note that some shenanigans are necessary here to support cross-database compatibility. For example, DuckDB has a `hugeint` data type, whereas Snowflake does not. Why does the small database need huge integers?)

When you run ADE-bench with the `--seed` flag, it will evaluate each trial with whatever CSVs exist in the `/seeds` directory _before_ the new ones are created, and then, _after the tests have run_, it will export the results into the directory. This means that you may need to run it twice to check that task works: Once to create the seeds, and another time (without the `--seed` flag) to see if it passes.

**ONLY RUN `--seed` WITH THE SAGE AGENT ON DUCKDB**. Exporting seeds is not currently supported with Snowflake, and because solution seeds are used as answer keys, they should never be created based on what an agent does.

---

## Contributing new dbt projects

dbt projects are stored in the `shared/projects/dbt` directory, and can be shared across tasks. When a task runs, the specified dbt project, which can be arbitrarily small or large, is loaded into the task environment and provided to the agent.

### Configuring dbt projects

When creating a dbt project, include the `profiles.yml` and `dbt_project.yml` file in the root directory of the project. In `profiles.yml`, include a profile for all of the supported databases, where the name is `[project_name]-[database_type]`. Do **NOT** fill in the Snowflake credentials, because these will get overwritten with the trial user:

```yaml
foo-duckdb:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: "./foo.duckdb"
      schema: main

foo-snowflake:
  target: dev
  outputs:
    dev:
      type: snowflake
      ## Added by ADE-bench when task is created
      account: <account>
      user: <user>
      password: <password>
      role: <role>
      database: <database>
      schema: <schema>
      warehouse: <warehouse>
```

### dbt Fusion

ADE-bench supports both dbt Core and dbt Fusion projects. When configuring a task, you can specify the project type as `dbt` or `dbt-fusion` in each variant in the `task.yaml` file:

```yaml
variants:
- db_type: duckdb
  db_name: foo
  project_type: dbt
  project_name: foo

- db_type: snowflake
  db_name: foo
  project_type: dbt-fusion
  project_name: foo
  migration_directory: foo__duckdb_to_snowflake_dbtf
```

### Migration scripts

You may need to modify the dbt project to work with different versions of dbt (or with different databases). This can be done with migration scripts.

In the example above, when the task is run against DuckDB, ADE-bench will copy the shared dbt project `foo` in the trial environment. When the task is run against Snowflake using dbt Fusion, it will copy the same project _and the contents of `shared/migrations/foo__duckdb_to_snowflake_dbtf`_. It will then run the `migration.sh` script prior to running the task `setup.sh` script.

Note that this migration script has access to any other files in that migration directory, so if you want to fully update some files in the dbt project, you can include the new files in the migration directory.

### Disabling static analysis

In some situations, the dbt Fusion engine's SQL Comprehension capabilities can make it impossible to build a misconfigured project. Disable static analysis by setting the environment variable `DBT_STATIC_ANALYSIS=off` in your invocation.

For example, this setup script alters a table to have a different data type. If static analysis is not turned off, the dbt run step will prematurely fail, preventing the setup script from completing successfully.

```bash
# Execute SQL using the run_sql utility.
/scripts/run_sql.sh "$@" << SQL
-- Update the due_at field to be an integer.
create or replace table main.task_data_temp as
  select
    * replace (due_at::integer as due_at)
  from main.task_data;
-- Rename the table to the original name.
drop table main.task_data;
alter table main.task_data_temp rename to task_data;
SQL

## Run the dbt project.
dbt deps
DBT_STATIC_ANALYSIS=off dbt run
```

Using the environment variable instead of the `--static-analysis off` flag ensures graceful degradation for dbt Core.

---

## Contributing new data

dbt projects need data to run against. The easiest way to share data is via a DuckDB database, which can be used as a both source database for a dbt project and its associated tasks, and as a source database of data to load into Snowflake. Tasks can then be run against Snowflake as well.

ADE-bench can automatically migrate DuckDB databases into Snowflake. For more, see the [README](/README#4-migrate-duckdb-databases-to-snowflake).

---

## Connecting to external projects and data sources

If you want to connect ADE-bench to your own dbt project or database, you can use the `project_dir` and `db_dir` fields in tasks' `task.yaml` files to specify directories containing your projects and databases:

```yaml
variants:
- db_type: duckdb
  db_name: mydb  # Will look for mydb.duckdb in db_dir
  db_dir: /path/to/my/databases  # Optional, directory containing database files
  project_type: dbt
  project_name: myproject  # Will look for 'myproject' folder in project_dir
  project_dir: /path/to/my/projects  # Optional, directory containing project folders
```

> [!CAUTION]
> If you connect ADE-bench to your own projects or databases, it can edit those projects and databases! Though ADE-bench can be useful framework for testing how agents perform real-world tasks on internal projects, we strongly recommend only running it in sandboxed environments. Agents can be unpredictable, and you should assume that it might delete anything that it has access to.

You can also use the `--tasks-dir` flag to point to a tasks directory outside the ADE-bench repository:

```bash
ade run foo001 --db duckdb --project-type dbt --tasks-dir /path/to/my/tasks
```
If you primarily want to use ADE-bench for these sorts of external tasks, you can set environment variables to change the default directories for all tasks, databases, and projects:

- `ADE_TASKS_DIR` - Default tasks directory (default: `tasks`)
- `ADE_DATABASES_DIR` - Default databases directory (default: `shared/databases`)
- `ADE_PROJECTS_DIR` - Default projects directory (default: `shared/projects`)

---

## Development tips

To develop a new task, there are a few things that can be useful:

- **Interactive mode:** You can run a task, and then launch an interactive shell into a task environment. You can also halt the task after different stages (e.g., after the setup scripts run but before the agent runs), and interact with the environment at that stage. This uses the `ade interact` command, and is [documented here](CLI.md).
- **Persist mode:** You can run the trial with the `--persist` flag, which keeps your Docker container alive after the task is complete. Then, you can log into the container—either directly, or via the Docker desktop app, and both look at the files in the container and run commands in a terminal.
- **Breakpoints:** You can insert a breakpoint function into the harness. To do this, find the point within the script that you want to halt the run and add code below. This will halt the harness at that point. If you run the harness with the `--persist` flag, the container will then be kept alive, as it was when the harness was halted.
- **Snowflake databases:** If you're working with Snowflake, the task will create task databases within your account (e.g., a task called `foo001` will create a database called `FOO001_DATABASE`). You can also query these directly.
