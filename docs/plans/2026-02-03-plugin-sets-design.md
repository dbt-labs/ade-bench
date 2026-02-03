# Design: Plugin Sets for ADE-Bench

**Status**: Ready for implementation
**Date**: 2026-02-03

## Overview

Replace the current `--use-mcp` and `--use-skills` flags with a YAML-configured plugin set system. This enables:

- A/B comparison of agent performance with different skill/MCP configurations
- Declarative configuration instead of CLI flags
- Reusable plugin types (skills, MCP) across multiple vendors

## Goals

1. Configure skill sets in YAML, reference by name from CLI
2. Support multiple default skill sets for automatic A/B comparison
3. Generic handlers for skills and MCP servers (not hardcoded per vendor)
4. Capture skill set metadata in results for analysis

## Non-Goals

- Transcript generation (separate feature, not in scope)
- Non-Claude agents for skills (skills via Vercel CLI are agent-agnostic, but some may only work with certain agents)

---

## Schema

**File:** `experiment_sets/skill-sets.yaml`

```yaml
sets:
  - name: no-plugins
    description: Baseline - no skills or MCP
    default: true
    # agents omitted = all agents compatible
    skills: []
    mcp_servers: {}
    allowed_tools: [Bash, Edit, Write, Read, Glob, Grep]

  - name: dbt-skills
    description: dbt skills via Vercel Skills CLI
    agents: [claude]  # Optional - restricts to specified agents
    skills:
      - dbt-labs/dbt-agent-skills
    mcp_servers: {}
    allowed_tools: [Bash, Edit, Write, Read, Glob, Grep, Skill]

  - name: dbt-mcp
    description: dbt MCP server
    default: true
    skills: []
    mcp_servers:
      dbt:
        command: uvx
        args: [dbt-mcp@latest]
        env:
          DISABLE_SEMANTIC_LAYER: "true"
          DISABLE_DISCOVERY: "true"
          DISABLE_ADMIN_API: "true"
          DISABLE_SQL: "true"
          DISABLE_DBT_CODEGEN: "true"
    allowed_tools: [Bash, Edit, Write, Read, Glob, Grep, mcp__dbt__*]

  - name: dbt-full
    description: Both skills and MCP
    agents: [claude]
    skills:
      - dbt-labs/dbt-agent-skills
    mcp_servers:
      dbt:
        command: uvx
        args: [dbt-mcp@latest]
        env:
          DISABLE_SEMANTIC_LAYER: "true"
          DISABLE_DISCOVERY: "true"
          DISABLE_ADMIN_API: "true"
          DISABLE_SQL: "true"
          DISABLE_DBT_CODEGEN: "true"
    allowed_tools: [Bash, Edit, Write, Read, Glob, Grep, Skill, mcp__dbt__*]
```

**Pydantic models** (`ade_bench/models/skill_set.py`):

```python
from pydantic import BaseModel

class McpServerConfig(BaseModel):
    command: str
    args: list[str] = []
    env: dict[str, str] = {}

class SkillSet(BaseModel):
    name: str
    description: str = ""
    default: bool = False
    agents: list[str] | None = None  # None = all agents compatible
    skills: list[str] = []
    mcp_servers: dict[str, McpServerConfig] = {}
    allowed_tools: list[str] = []

class SkillSetsConfig(BaseModel):
    sets: list[SkillSet]
```

---

## CLI Changes

**Remove:**
- `--use-mcp`
- `--use-skills`

**Add:**
- `--plugin-set` (space-separated list of skill set names)

**Behavior:**

```bash
# No flag: runs all default skill sets (A/B comparison)
ab run task001 --db duckdb --project-type dbt --agent claude
# Runs: no-plugins, dbt-mcp (both marked default: true)

# Explicit single set
ab run task001 --db duckdb --project-type dbt --agent claude --plugin-set dbt-skills

# Explicit multiple sets (space-separated)
ab run task001 --db duckdb --project-type dbt --agent claude --plugin-set no-plugins dbt-mcp
```

**Validation at startup:**
1. Load `experiment_sets/skill-sets.yaml`
2. If `--plugin-set` specified, validate names exist; otherwise use defaults
3. Filter to skill sets compatible with `--agent`
4. Error and exit if no compatible skill sets remain
5. Run separate trials for each skill set

---

## Plugin Type Handlers

Two generic handlers read from skill set config:

### SkillsHandler

Installs skills via Vercel Skills CLI. Refactored from existing `_install_skills_via_cli()`.

```python
class SkillsHandler:
    def install(self, skill_set: SkillSet, terminal) -> None:
        for repo in skill_set.skills:
            cmd = f"npx --yes skills add {repo} --all"
            result = terminal.container.exec_run(
                ["sh", "-c", cmd],
                workdir="/app"
            )
            if result.exit_code != 0:
                raise RuntimeError(f"Skills installation failed: {result.output}")
```

### McpHandler

Configures MCP servers in agent config. Static env vars from YAML; dynamic vars (`DBT_PROJECT_DIR`, `DBT_PATH`) set during container setup.

```python
class McpHandler:
    def configure(self, skill_set: SkillSet, agent_name: str, terminal) -> None:
        for name, config in skill_set.mcp_servers.items():
            # Write env file
            env_content = "\n".join(f"{k}={v}" for k, v in config.env.items())
            env_path = f"/tmp/{name}.env"
            terminal.container.exec_run(["sh", "-c", f"cat > {env_path} << 'EOF'\n{env_content}\nEOF"])

            # Register with agent
            args_str = " ".join(config.args)
            cmd = f"{agent_name} mcp add {name} -- {config.command} --env-file {env_path} {args_str}"
            terminal.container.exec_run(["sh", "-c", cmd], workdir="/app")
```

Both handlers run in the `pre_agent` phase (after setup, before agent starts).

---

## Output Structure

Each skill set produces a separate run with suffixed run_id:

```
experiments/
├── 2026-02-03__14-30-00__no-plugins/
│   ├── run_config.yaml
│   ├── results.json
│   └── task_001.duckdb_dbt/
│       ├── result.json
│       └── agent-logs/
│
└── 2026-02-03__14-30-00__dbt-mcp/
    ├── run_config.yaml
    ├── results.json
    └── task_001.duckdb_dbt/
        ├── result.json
        └── agent-logs/
```

### Result Metadata

**result.json** (per task):
```json
{
  "task_id": "task_001.duckdb_dbt",
  "agent": "claude",
  "pass": true,
  "runtime_ms": 45000,
  "skill_set": {
    "name": "dbt-mcp",
    "skills": [],
    "mcp_servers": ["dbt"]
  }
}
```

**results.json** (aggregated, at run level):
```json
{
  "run_id": "2026-02-03__14-30-00__dbt-mcp",
  "skill_set": {
    "name": "dbt-mcp",
    "skills": [],
    "mcp_servers": {
      "dbt": {
        "command": "uvx",
        "args": ["dbt-mcp@latest"],
        "env": {
          "DISABLE_SEMANTIC_LAYER": "true"
        }
      }
    }
  },
  "trials": [...]
}
```

---

## Implementation Plan

### New Files

| File | Purpose |
|------|---------|
| `experiment_sets/skill-sets.yaml` | Skill set definitions |
| `ade_bench/models/skill_set.py` | Pydantic models for schema |
| `ade_bench/plugins/skills_handler.py` | Installs skills via `npx skills add` |
| `ade_bench/plugins/mcp_handler.py` | Configures MCP servers |
| `ade_bench/plugins/skill_set_loader.py` | Loads and validates YAML config |

### Files to Modify

| File | Changes |
|------|---------|
| `ade_bench/cli/ab/main.py` | Remove `--use-mcp`, `--use-skills`; add `--plugin-set` |
| `ade_bench/harness.py` | Loop over skill sets, suffix run_id |
| `ade_bench/setup/agent_setup.py` | Remove `_install_skills_via_cli()`, `use_skills` param |
| `ade_bench/setup/setup_orchestrator.py` | Call handlers based on skill set config |
| Container setup scripts | Set `DBT_PROJECT_DIR`, `DBT_PATH` env vars |
| `ade_bench/models/results.py` | Add skill_set field to result models |

### Files to Delete

| File | Reason |
|------|--------|
| `shared/scripts/setup-dbt-mcp.sh` | Logic moves to `McpHandler` |

---

## Open Questions

None - design is ready for implementation.
