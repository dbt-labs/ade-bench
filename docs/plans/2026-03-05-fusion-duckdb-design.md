# Fusion + DuckDB Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add dbt Fusion engine support for DuckDB tasks, so the benchmark can evaluate AI agents running Fusion instead of dbt-core on DuckDB.

**Architecture:** Mirror the existing Snowflake Fusion pattern. New Dockerfile + docker-compose, one routing change in the harness, and a new variant added to all 44 DuckDB tasks.

**Tech Stack:** Docker, dbt Fusion (latest), DuckDB, Python

---

### Task 1: Create Dockerfile.duckdb-dbtf

**Files:**
- Create: `docker/base/Dockerfile.duckdb-dbtf`

**Step 1: Create the Dockerfile**

```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    git \
    tmux asciinema \
    curl \
    && curl -sSL https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64 \
        -o /usr/bin/yq \
    && chmod +x /usr/bin/yq \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install dbt Fusion
RUN export SHELL=/bin/bash && \
    curl -fsSL https://public.cdn.getdbt.com/fs/install/install.sh | sh -s -- --update

# Install DuckDB Python package (needed for Fusion DuckDB connections)
RUN pip install --no-cache-dir \
    duckdb \
    pyyaml>=6.0 \
    uv>=0.7

# Set up workspace
RUN mkdir -p /installed-agent /scripts /sage/solutions /sage /app /app/setup /app/migrations /seeds /solutions /logs /tests
WORKDIR /app

CMD ["bash"]
```

**Step 2: Commit**

```bash
git add docker/base/Dockerfile.duckdb-dbtf
git commit -m "feat: add Dockerfile for dbt Fusion + DuckDB"
```

---

### Task 2: Create docker-compose-duckdb-dbtf.yaml

**Files:**
- Create: `shared/defaults/docker-compose-duckdb-dbtf.yaml`

**Step 1: Create the compose file**

```yaml
services:
  client:
    build:
      context: ${T_BENCH_REPO_ROOT}
      dockerfile: docker/base/Dockerfile.duckdb-dbtf
    image: ${T_BENCH_TASK_DOCKER_CLIENT_IMAGE_NAME}
    container_name: ${T_BENCH_TASK_DOCKER_CLIENT_CONTAINER_NAME}
    command: [ "sh", "-c", "sleep infinity" ]
    environment:
      - TEST_DIR=${T_BENCH_TEST_DIR}
    volumes:
      - ${T_BENCH_TASK_LOGS_PATH}:${T_BENCH_CONTAINER_LOGS_PATH}
```

**Step 2: Commit**

```bash
git add shared/defaults/docker-compose-duckdb-dbtf.yaml
git commit -m "feat: add docker-compose for dbt Fusion + DuckDB"
```

---

### Task 3: Update harness routing in trial_handler.py

**Files:**
- Modify: `ade_bench/handlers/trial_handler.py:307-312`

**Step 1: Update the routing logic**

Change the `docker_compose_path` property. Replace lines 311-312:

```python
elif db_type == "duckdb":
    return self._defaults_path / "docker-compose-duckdb-dbt.yaml"
```

With:

```python
elif db_type == "duckdb" and project_type == "dbt-fusion":
    return self._defaults_path / "docker-compose-duckdb-dbtf.yaml"
elif db_type == "duckdb":
    return self._defaults_path / "docker-compose-duckdb-dbt.yaml"
```

**Step 2: Commit**

```bash
git add ade_bench/handlers/trial_handler.py
git commit -m "feat: route duckdb+fusion to new docker-compose"
```

---

### Task 4: Add dbt-fusion variant to all 44 DuckDB tasks

**Files:**
- Modify: All 44 `tasks/*/task.yaml` files that have a `db_type: duckdb` variant

**Step 1: Add the variant using a script**

For each task, append a new variant block after the existing variants:

```yaml
- db_type: duckdb
  db_name: <same as existing duckdb variant>
  project_type: dbt-fusion
  project_name: <same as existing duckdb variant>
```

Run a Python script to do this programmatically across all 44 tasks.

**Step 2: Spot-check a few files** to verify the variant was added correctly.

**Step 3: Commit**

```bash
git add tasks/*/task.yaml
git commit -m "feat: add duckdb+fusion variant to all DuckDB tasks"
```
