# Plugin Sets Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace `--use-mcp` and `--use-skills` flags with YAML-configured plugin sets for A/B comparison.

**Architecture:** Define skill sets in `experiment_sets/skill-sets.yaml`, load via Pydantic models, apply via generic handlers (SkillsHandler, McpHandler) in pre-agent phase. Multiple default sets run as separate trials with suffixed run IDs.

**Tech Stack:** Python 3.11+, Pydantic, PyYAML, typer CLI

---

## Task 1: Create Pydantic Models for Skill Sets

**Files:**
- Create: `ade_bench/models/__init__.py`
- Create: `ade_bench/models/skill_set.py`
- Test: `tests/models/test_skill_set.py`

**Step 1: Create models directory**

```bash
mkdir -p ade_bench/models tests/models
touch ade_bench/models/__init__.py tests/models/__init__.py
```

**Step 2: Write the failing test**

Create `tests/models/test_skill_set.py`:

```python
import pytest
from ade_bench.models.skill_set import SkillSet, McpServerConfig, SkillSetsConfig


def test_mcp_server_config_minimal():
    config = McpServerConfig(command="uvx", args=["dbt-mcp@latest"])
    assert config.command == "uvx"
    assert config.args == ["dbt-mcp@latest"]
    assert config.env == {}


def test_mcp_server_config_with_env():
    config = McpServerConfig(
        command="uvx",
        args=["dbt-mcp@latest"],
        env={"DISABLE_SQL": "true"}
    )
    assert config.env == {"DISABLE_SQL": "true"}


def test_skill_set_minimal():
    skill_set = SkillSet(name="test", allowed_tools=["Bash"])
    assert skill_set.name == "test"
    assert skill_set.description == ""
    assert skill_set.default is False
    assert skill_set.agents is None
    assert skill_set.skills == []
    assert skill_set.mcp_servers == {}
    assert skill_set.allowed_tools == ["Bash"]


def test_skill_set_full():
    skill_set = SkillSet(
        name="dbt-full",
        description="Full dbt setup",
        default=True,
        agents=["claude"],
        skills=["dbt-labs/dbt-agent-skills"],
        mcp_servers={
            "dbt": McpServerConfig(command="uvx", args=["dbt-mcp@latest"])
        },
        allowed_tools=["Bash", "Skill", "mcp__dbt__*"]
    )
    assert skill_set.default is True
    assert skill_set.agents == ["claude"]
    assert len(skill_set.mcp_servers) == 1


def test_skill_set_is_compatible_with_agent_all():
    """When agents is None, compatible with all agents."""
    skill_set = SkillSet(name="test", allowed_tools=["Bash"])
    assert skill_set.is_compatible_with_agent("claude") is True
    assert skill_set.is_compatible_with_agent("gemini") is True


def test_skill_set_is_compatible_with_agent_restricted():
    """When agents is set, only compatible with listed agents."""
    skill_set = SkillSet(name="test", agents=["claude"], allowed_tools=["Bash"])
    assert skill_set.is_compatible_with_agent("claude") is True
    assert skill_set.is_compatible_with_agent("gemini") is False


def test_skill_sets_config_from_yaml():
    yaml_content = """
sets:
  - name: no-plugins
    default: true
    skills: []
    allowed_tools: [Bash, Read]
  - name: dbt-skills
    agents: [claude]
    skills:
      - dbt-labs/dbt-agent-skills
    allowed_tools: [Bash, Skill]
"""
    import yaml
    data = yaml.safe_load(yaml_content)
    config = SkillSetsConfig(**data)
    assert len(config.sets) == 2
    assert config.sets[0].name == "no-plugins"
    assert config.sets[0].default is True


def test_skill_sets_config_get_defaults():
    config = SkillSetsConfig(sets=[
        SkillSet(name="a", default=True, allowed_tools=["Bash"]),
        SkillSet(name="b", default=False, allowed_tools=["Bash"]),
        SkillSet(name="c", default=True, allowed_tools=["Bash"]),
    ])
    defaults = config.get_defaults()
    assert len(defaults) == 2
    assert defaults[0].name == "a"
    assert defaults[1].name == "c"


def test_skill_sets_config_get_by_name():
    config = SkillSetsConfig(sets=[
        SkillSet(name="a", allowed_tools=["Bash"]),
        SkillSet(name="b", allowed_tools=["Bash"]),
    ])
    assert config.get_by_name("a").name == "a"
    assert config.get_by_name("b").name == "b"
    assert config.get_by_name("nonexistent") is None


def test_skill_sets_config_get_by_names():
    config = SkillSetsConfig(sets=[
        SkillSet(name="a", allowed_tools=["Bash"]),
        SkillSet(name="b", allowed_tools=["Bash"]),
        SkillSet(name="c", allowed_tools=["Bash"]),
    ])
    result = config.get_by_names(["a", "c"])
    assert len(result) == 2
    assert result[0].name == "a"
    assert result[1].name == "c"


def test_skill_sets_config_get_by_names_unknown_raises():
    config = SkillSetsConfig(sets=[
        SkillSet(name="a", allowed_tools=["Bash"]),
    ])
    with pytest.raises(ValueError, match="Unknown skill set"):
        config.get_by_names(["a", "nonexistent"])
```

**Step 3: Run test to verify it fails**

Run: `uv run pytest tests/models/test_skill_set.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'ade_bench.models.skill_set'"

**Step 4: Write the implementation**

Create `ade_bench/models/skill_set.py`:

```python
"""Pydantic models for skill set configuration."""

from pydantic import BaseModel


class McpServerConfig(BaseModel):
    """Configuration for an MCP server."""
    command: str
    args: list[str] = []
    env: dict[str, str] = {}


class SkillSet(BaseModel):
    """Configuration for a set of skills and tools."""
    name: str
    description: str = ""
    default: bool = False
    agents: list[str] | None = None  # None = all agents compatible
    skills: list[str] = []
    mcp_servers: dict[str, McpServerConfig] = {}
    allowed_tools: list[str] = []

    def is_compatible_with_agent(self, agent_name: str) -> bool:
        """Check if this skill set is compatible with the given agent."""
        if self.agents is None:
            return True
        return agent_name in self.agents


class SkillSetsConfig(BaseModel):
    """Root configuration containing all skill sets."""
    sets: list[SkillSet]

    def get_defaults(self) -> list[SkillSet]:
        """Get all skill sets marked as default."""
        return [s for s in self.sets if s.default]

    def get_by_name(self, name: str) -> SkillSet | None:
        """Get a skill set by name."""
        for s in self.sets:
            if s.name == name:
                return s
        return None

    def get_by_names(self, names: list[str]) -> list[SkillSet]:
        """Get multiple skill sets by name. Raises if any not found."""
        result = []
        for name in names:
            skill_set = self.get_by_name(name)
            if skill_set is None:
                available = [s.name for s in self.sets]
                raise ValueError(
                    f"Unknown skill set '{name}'. Available: {', '.join(available)}"
                )
            result.append(skill_set)
        return result
```

Update `ade_bench/models/__init__.py`:

```python
"""Models for ADE-Bench configuration."""

from .skill_set import McpServerConfig, SkillSet, SkillSetsConfig

__all__ = ["McpServerConfig", "SkillSet", "SkillSetsConfig"]
```

**Step 5: Run test to verify it passes**

Run: `uv run pytest tests/models/test_skill_set.py -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add ade_bench/models/ tests/models/
git commit -m "feat: add Pydantic models for skill set configuration"
```

---

## Task 2: Create Skill Sets YAML File

**Files:**
- Create: `experiment_sets/skill-sets.yaml`

**Step 1: Create the YAML file**

Create `experiment_sets/skill-sets.yaml`:

```yaml
# Skill set configurations for ADE-Bench
# Use --plugin-set <name> to select, or run without flag to use all defaults

sets:
  - name: no-plugins
    description: Baseline - no skills or MCP
    default: true
    skills: []
    mcp_servers: {}
    allowed_tools: [Bash, Edit, Write, Read, Glob, Grep]

  - name: dbt-skills
    description: dbt skills via Vercel Skills CLI
    agents: [claude]
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

**Step 2: Commit**

```bash
git add experiment_sets/skill-sets.yaml
git commit -m "feat: add skill-sets.yaml configuration"
```

---

## Task 3: Create Skill Set Loader

**Files:**
- Create: `ade_bench/plugins/__init__.py`
- Create: `ade_bench/plugins/loader.py`
- Test: `tests/plugins/test_loader.py`

**Step 1: Create plugins directory**

```bash
mkdir -p ade_bench/plugins tests/plugins
touch ade_bench/plugins/__init__.py tests/plugins/__init__.py
```

**Step 2: Write the failing test**

Create `tests/plugins/test_loader.py`:

```python
import pytest
from pathlib import Path
from ade_bench.plugins.loader import SkillSetLoader
from ade_bench.models.skill_set import SkillSetsConfig


def test_loader_loads_yaml(tmp_path):
    yaml_file = tmp_path / "skill-sets.yaml"
    yaml_file.write_text("""
sets:
  - name: test
    default: true
    skills: []
    allowed_tools: [Bash]
""")
    loader = SkillSetLoader(yaml_file)
    config = loader.load()
    assert isinstance(config, SkillSetsConfig)
    assert len(config.sets) == 1
    assert config.sets[0].name == "test"


def test_loader_file_not_found():
    loader = SkillSetLoader(Path("/nonexistent/skill-sets.yaml"))
    with pytest.raises(FileNotFoundError):
        loader.load()


def test_loader_resolve_skill_sets_explicit():
    """Explicit --plugin-set names are resolved."""
    yaml_content = """
sets:
  - name: a
    default: false
    allowed_tools: [Bash]
  - name: b
    default: true
    allowed_tools: [Bash]
"""
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_content)
        f.flush()
        loader = SkillSetLoader(Path(f.name))
        result = loader.resolve_skill_sets(
            plugin_set_names=["a"],
            agent_name="claude"
        )
        assert len(result) == 1
        assert result[0].name == "a"


def test_loader_resolve_skill_sets_defaults():
    """When no --plugin-set, use defaults."""
    yaml_content = """
sets:
  - name: a
    default: false
    allowed_tools: [Bash]
  - name: b
    default: true
    allowed_tools: [Bash]
  - name: c
    default: true
    allowed_tools: [Bash]
"""
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_content)
        f.flush()
        loader = SkillSetLoader(Path(f.name))
        result = loader.resolve_skill_sets(
            plugin_set_names=None,
            agent_name="claude"
        )
        assert len(result) == 2
        assert result[0].name == "b"
        assert result[1].name == "c"


def test_loader_resolve_skill_sets_filters_incompatible():
    """Skill sets incompatible with agent are filtered out."""
    yaml_content = """
sets:
  - name: claude-only
    default: true
    agents: [claude]
    allowed_tools: [Bash]
  - name: all-agents
    default: true
    allowed_tools: [Bash]
"""
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_content)
        f.flush()
        loader = SkillSetLoader(Path(f.name))

        # Claude gets both
        result = loader.resolve_skill_sets(None, "claude")
        assert len(result) == 2

        # Gemini only gets all-agents
        result = loader.resolve_skill_sets(None, "gemini")
        assert len(result) == 1
        assert result[0].name == "all-agents"


def test_loader_resolve_skill_sets_error_on_incompatible_explicit():
    """Error when explicitly requested skill set is incompatible."""
    yaml_content = """
sets:
  - name: claude-only
    agents: [claude]
    allowed_tools: [Bash]
"""
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_content)
        f.flush()
        loader = SkillSetLoader(Path(f.name))

        with pytest.raises(ValueError, match="not compatible with agent 'gemini'"):
            loader.resolve_skill_sets(["claude-only"], "gemini")


def test_loader_resolve_skill_sets_error_when_none_compatible():
    """Error when no skill sets are compatible with agent."""
    yaml_content = """
sets:
  - name: claude-only
    default: true
    agents: [claude]
    allowed_tools: [Bash]
"""
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_content)
        f.flush()
        loader = SkillSetLoader(Path(f.name))

        with pytest.raises(ValueError, match="No compatible skill sets"):
            loader.resolve_skill_sets(None, "gemini")
```

**Step 3: Run test to verify it fails**

Run: `uv run pytest tests/plugins/test_loader.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'ade_bench.plugins.loader'"

**Step 4: Write the implementation**

Create `ade_bench/plugins/loader.py`:

```python
"""Loader for skill set configuration."""

from pathlib import Path
import yaml

from ade_bench.models.skill_set import SkillSet, SkillSetsConfig


class SkillSetLoader:
    """Loads and resolves skill sets from YAML configuration."""

    def __init__(self, config_path: Path):
        self._config_path = config_path
        self._config: SkillSetsConfig | None = None

    def load(self) -> SkillSetsConfig:
        """Load the skill sets configuration from YAML."""
        if not self._config_path.exists():
            raise FileNotFoundError(f"Skill sets config not found: {self._config_path}")

        with open(self._config_path) as f:
            data = yaml.safe_load(f)

        self._config = SkillSetsConfig(**data)
        return self._config

    def resolve_skill_sets(
        self,
        plugin_set_names: list[str] | None,
        agent_name: str,
    ) -> list[SkillSet]:
        """Resolve which skill sets to use for a run.

        Args:
            plugin_set_names: Explicit skill set names from --plugin-set, or None for defaults
            agent_name: The agent being used (e.g., "claude", "gemini")

        Returns:
            List of SkillSet objects to use

        Raises:
            ValueError: If requested skill set is not found or incompatible
        """
        if self._config is None:
            self.load()

        # Get skill sets (explicit or defaults)
        if plugin_set_names:
            skill_sets = self._config.get_by_names(plugin_set_names)
            # Validate all are compatible with agent
            for ss in skill_sets:
                if not ss.is_compatible_with_agent(agent_name):
                    raise ValueError(
                        f"Skill set '{ss.name}' is not compatible with agent '{agent_name}'. "
                        f"Compatible agents: {ss.agents}"
                    )
        else:
            skill_sets = self._config.get_defaults()

        # Filter to compatible skill sets
        compatible = [ss for ss in skill_sets if ss.is_compatible_with_agent(agent_name)]

        if not compatible:
            if plugin_set_names:
                raise ValueError(
                    f"No compatible skill sets found for agent '{agent_name}' "
                    f"from requested: {plugin_set_names}"
                )
            else:
                raise ValueError(
                    f"No compatible skill sets found for agent '{agent_name}'. "
                    f"No default skill sets are compatible with this agent."
                )

        return compatible
```

Update `ade_bench/plugins/__init__.py`:

```python
"""Plugin system for ADE-Bench."""

from .loader import SkillSetLoader

__all__ = ["SkillSetLoader"]
```

**Step 5: Run test to verify it passes**

Run: `uv run pytest tests/plugins/test_loader.py -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add ade_bench/plugins/ tests/plugins/
git commit -m "feat: add SkillSetLoader to load and resolve skill sets"
```

---

## Task 4: Create SkillsHandler

**Files:**
- Create: `ade_bench/plugins/skills_handler.py`
- Test: `tests/plugins/test_skills_handler.py`

**Step 1: Write the failing test**

Create `tests/plugins/test_skills_handler.py`:

```python
import pytest
from unittest.mock import MagicMock, call
from ade_bench.plugins.skills_handler import SkillsHandler
from ade_bench.models.skill_set import SkillSet


def test_skills_handler_install_no_skills():
    """No-op when skill set has no skills."""
    skill_set = SkillSet(name="test", skills=[], allowed_tools=["Bash"])
    terminal = MagicMock()

    handler = SkillsHandler()
    handler.install(skill_set, terminal)

    terminal.container.exec_run.assert_not_called()


def test_skills_handler_install_single_skill():
    """Installs a single skill repo."""
    skill_set = SkillSet(
        name="test",
        skills=["dbt-labs/dbt-agent-skills"],
        allowed_tools=["Bash"]
    )
    terminal = MagicMock()
    terminal.container.exec_run.return_value = MagicMock(exit_code=0, output=b"Success")

    handler = SkillsHandler()
    handler.install(skill_set, terminal)

    terminal.container.exec_run.assert_called_once()
    call_args = terminal.container.exec_run.call_args
    cmd = call_args[0][0]
    assert "npx" in cmd[2]
    assert "skills add" in cmd[2]
    assert "dbt-labs/dbt-agent-skills" in cmd[2]


def test_skills_handler_install_multiple_skills():
    """Installs multiple skill repos."""
    skill_set = SkillSet(
        name="test",
        skills=["repo/a", "repo/b"],
        allowed_tools=["Bash"]
    )
    terminal = MagicMock()
    terminal.container.exec_run.return_value = MagicMock(exit_code=0, output=b"Success")

    handler = SkillsHandler()
    handler.install(skill_set, terminal)

    assert terminal.container.exec_run.call_count == 2


def test_skills_handler_install_failure_logs_warning():
    """Logs warning but doesn't raise on install failure."""
    skill_set = SkillSet(
        name="test",
        skills=["repo/failing"],
        allowed_tools=["Bash"]
    )
    terminal = MagicMock()
    terminal.container.exec_run.return_value = MagicMock(
        exit_code=1,
        output=b"npm ERR! not found"
    )

    handler = SkillsHandler()
    # Should not raise, just log warning
    handler.install(skill_set, terminal)
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/plugins/test_skills_handler.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'ade_bench.plugins.skills_handler'"

**Step 3: Write the implementation**

Create `ade_bench/plugins/skills_handler.py`:

```python
"""Handler for installing skills via Vercel Skills CLI."""

import logging
from ade_bench.models.skill_set import SkillSet
from ade_bench.terminal.docker_compose_manager import DockerComposeManager

logger = logging.getLogger(__name__)


class SkillsHandler:
    """Installs skills from skill set configuration."""

    def install(self, skill_set: SkillSet, terminal: DockerComposeManager) -> None:
        """Install skills from the skill set into the container.

        Args:
            skill_set: The skill set configuration
            terminal: The Docker container manager
        """
        if not skill_set.skills:
            logger.debug(f"[SkillsHandler] No skills to install for '{skill_set.name}'")
            return

        for repo in skill_set.skills:
            cmd = f"npx --yes skills add {repo} --all"
            logger.info(f"[SkillsHandler] Installing skills from {repo}...")

            result = terminal.container.exec_run(
                ["sh", "-c", cmd],
                workdir=str(DockerComposeManager.CONTAINER_APP_DIR)
            )

            if result.exit_code != 0:
                logger.warning(
                    f"[SkillsHandler] Skills installation failed for {repo}: "
                    f"{result.output.decode('utf-8')}"
                )
            else:
                logger.info(f"[SkillsHandler] Skills installed successfully from {repo}")
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/plugins/test_skills_handler.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add ade_bench/plugins/skills_handler.py tests/plugins/test_skills_handler.py
git commit -m "feat: add SkillsHandler for installing skills"
```

---

## Task 5: Create McpHandler

**Files:**
- Create: `ade_bench/plugins/mcp_handler.py`
- Test: `tests/plugins/test_mcp_handler.py`

**Step 1: Write the failing test**

Create `tests/plugins/test_mcp_handler.py`:

```python
import pytest
from unittest.mock import MagicMock, call
from ade_bench.plugins.mcp_handler import McpHandler
from ade_bench.models.skill_set import SkillSet, McpServerConfig


def test_mcp_handler_configure_no_servers():
    """No-op when skill set has no MCP servers."""
    skill_set = SkillSet(name="test", mcp_servers={}, allowed_tools=["Bash"])
    terminal = MagicMock()

    handler = McpHandler()
    handler.configure(skill_set, "claude", terminal)

    terminal.container.exec_run.assert_not_called()


def test_mcp_handler_configure_single_server():
    """Configures a single MCP server."""
    skill_set = SkillSet(
        name="test",
        mcp_servers={
            "dbt": McpServerConfig(command="uvx", args=["dbt-mcp@latest"])
        },
        allowed_tools=["Bash"]
    )
    terminal = MagicMock()
    terminal.container.exec_run.return_value = MagicMock(exit_code=0, output=b"Success")

    handler = McpHandler()
    handler.configure(skill_set, "claude", terminal)

    # Should have at least one call for mcp add
    assert terminal.container.exec_run.call_count >= 1
    calls = terminal.container.exec_run.call_args_list
    # Find the mcp add call
    mcp_add_call = [c for c in calls if "mcp add" in str(c)]
    assert len(mcp_add_call) >= 1


def test_mcp_handler_configure_with_env():
    """Writes env file when env vars are specified."""
    skill_set = SkillSet(
        name="test",
        mcp_servers={
            "dbt": McpServerConfig(
                command="uvx",
                args=["dbt-mcp@latest"],
                env={"DISABLE_SQL": "true", "DISABLE_DISCOVERY": "true"}
            )
        },
        allowed_tools=["Bash"]
    )
    terminal = MagicMock()
    terminal.container.exec_run.return_value = MagicMock(exit_code=0, output=b"Success")

    handler = McpHandler()
    handler.configure(skill_set, "claude", terminal)

    # Check that env file was written
    calls = terminal.container.exec_run.call_args_list
    env_write_calls = [c for c in calls if "DISABLE_SQL" in str(c)]
    assert len(env_write_calls) >= 1


def test_mcp_handler_configure_different_agents():
    """Uses correct agent CLI command."""
    skill_set = SkillSet(
        name="test",
        mcp_servers={
            "dbt": McpServerConfig(command="uvx", args=["dbt-mcp"])
        },
        allowed_tools=["Bash"]
    )
    terminal = MagicMock()
    terminal.container.exec_run.return_value = MagicMock(exit_code=0, output=b"Success")

    handler = McpHandler()

    # Test claude
    handler.configure(skill_set, "claude", terminal)
    calls = terminal.container.exec_run.call_args_list
    claude_calls = [c for c in calls if "claude mcp add" in str(c)]
    assert len(claude_calls) >= 1

    terminal.reset_mock()

    # Test gemini
    handler.configure(skill_set, "gemini", terminal)
    calls = terminal.container.exec_run.call_args_list
    gemini_calls = [c for c in calls if "gemini mcp add" in str(c)]
    assert len(gemini_calls) >= 1
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/plugins/test_mcp_handler.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'ade_bench.plugins.mcp_handler'"

**Step 3: Write the implementation**

Create `ade_bench/plugins/mcp_handler.py`:

```python
"""Handler for configuring MCP servers."""

import logging
from ade_bench.models.skill_set import SkillSet
from ade_bench.terminal.docker_compose_manager import DockerComposeManager

logger = logging.getLogger(__name__)


class McpHandler:
    """Configures MCP servers from skill set configuration."""

    def configure(self, skill_set: SkillSet, agent_name: str, terminal: DockerComposeManager) -> None:
        """Configure MCP servers for the agent.

        Args:
            skill_set: The skill set configuration
            agent_name: The agent CLI name (claude, gemini, codex)
            terminal: The Docker container manager
        """
        if not skill_set.mcp_servers:
            logger.debug(f"[McpHandler] No MCP servers to configure for '{skill_set.name}'")
            return

        for server_name, config in skill_set.mcp_servers.items():
            logger.info(f"[McpHandler] Configuring MCP server '{server_name}'...")

            # Write env file if env vars specified
            env_file_path = None
            if config.env:
                env_file_path = f"/tmp/{server_name}.env"
                env_content = "\n".join(f"{k}={v}" for k, v in config.env.items())
                write_cmd = f"cat > {env_file_path} << 'ENVEOF'\n{env_content}\nENVEOF"

                result = terminal.container.exec_run(
                    ["sh", "-c", write_cmd],
                    workdir=str(DockerComposeManager.CONTAINER_APP_DIR)
                )
                if result.exit_code != 0:
                    logger.warning(f"[McpHandler] Failed to write env file: {result.output.decode('utf-8')}")

            # Build mcp add command
            args_str = " ".join(config.args)
            if env_file_path:
                mcp_cmd = f"{agent_name} mcp add {server_name} -- {config.command} --env-file {env_file_path} {args_str}"
            else:
                mcp_cmd = f"{agent_name} mcp add {server_name} -- {config.command} {args_str}"

            logger.info(f"[McpHandler] Running: {mcp_cmd}")
            result = terminal.container.exec_run(
                ["sh", "-c", mcp_cmd],
                workdir=str(DockerComposeManager.CONTAINER_APP_DIR)
            )

            if result.exit_code != 0:
                logger.warning(
                    f"[McpHandler] MCP server registration failed for {server_name}: "
                    f"{result.output.decode('utf-8')}"
                )
            else:
                logger.info(f"[McpHandler] MCP server '{server_name}' configured successfully")
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/plugins/test_mcp_handler.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add ade_bench/plugins/mcp_handler.py tests/plugins/test_mcp_handler.py
git commit -m "feat: add McpHandler for configuring MCP servers"
```

---

## Task 6: Update harness_models.py with Skill Set Metadata

**Files:**
- Modify: `ade_bench/harness_models.py:76-98` (TrialResults class)

**Step 1: Update TrialResults model**

Edit `ade_bench/harness_models.py` to add skill_set field to TrialResults:

Find this section (around line 76):
```python
class TrialResults(BaseModel):
    trial_name: str
    task_id: str
    ...
    used_mcp: bool | None = None
```

Replace `used_mcp: bool | None = None` with:

```python
    # Skill set metadata
    skill_set_name: str | None = None
    skill_set_skills: list[str] | None = None
    skill_set_mcp_servers: list[str] | None = None
```

**Step 2: Run existing tests**

Run: `uv run pytest tests/ -v -k "not slow"`
Expected: All tests PASS (model change is additive)

**Step 3: Commit**

```bash
git add ade_bench/harness_models.py
git commit -m "feat: add skill set metadata to TrialResults model"
```

---

## Task 7: Update CLI to Add --plugin-set Flag

**Files:**
- Modify: `ade_bench/cli/ab/main.py`

**Step 1: Update CLI**

Edit `ade_bench/cli/ab/main.py`:

1. Remove these options from the `run` command:
```python
    use_mcp: bool = typer.Option(
        False,
        "--use-mcp",
        help="Enable MCP (Model Context Protocol) for the agent"
    ),
    use_skills: bool = typer.Option(
        False,
        "--use-skills",
        help="Enable skills for the agent (e.g., dbt-debugging skill)"
    ),
```

2. Add this option after `log_level`:
```python
    plugin_set: list[str] = typer.Option(
        None,
        "--plugin-set",
        help="Space-separated skill set names from skill-sets.yaml (default: use all default sets)"
    ),
```

3. Update the Harness instantiation to remove `use_mcp` and `use_skills`, add `plugin_set_names`:

Find:
```python
    harness = Harness(
        ...
        use_mcp=use_mcp,
        use_skills=use_skills,
        with_profiling=with_profiling
    )
```

Replace with:
```python
    harness = Harness(
        ...
        plugin_set_names=plugin_set,
        with_profiling=with_profiling
    )
```

**Step 2: Verify CLI help**

Run: `uv run ab run --help`
Expected: Shows `--plugin-set` option, no `--use-mcp` or `--use-skills`

**Step 3: Commit**

```bash
git add ade_bench/cli/ab/main.py
git commit -m "feat: replace --use-mcp and --use-skills with --plugin-set"
```

---

## Task 8: Update Harness to Use Skill Sets

**Files:**
- Modify: `ade_bench/harness.py`

**Step 1: Update Harness.__init__**

Edit `ade_bench/harness.py`:

1. Add imports at top:
```python
from ade_bench.plugins.loader import SkillSetLoader
from ade_bench.models.skill_set import SkillSet
```

2. Update `__init__` signature - remove `use_mcp` and `use_skills`, add `plugin_set_names`:

Find:
```python
        use_mcp: bool = False,
        use_skills: bool = False,
```

Replace with:
```python
        plugin_set_names: list[str] | None = None,
```

3. Update instance variables in `__init__`:

Find:
```python
        self._use_mcp = use_mcp
        self._use_skills = use_skills
```

Replace with:
```python
        self._plugin_set_names = plugin_set_names
        self._skill_sets: list[SkillSet] = []
```

4. Add skill set loading after `self._init_dataset()`:

```python
        self._init_dataset()
        self._init_skill_sets()
        self._init_logger()
```

5. Add the new method:

```python
    def _init_skill_sets(self) -> None:
        """Load and resolve skill sets from configuration."""
        config_path = self._dataset_path.parent / "experiment_sets" / "skill-sets.yaml"
        loader = SkillSetLoader(config_path)
        self._skill_sets = loader.resolve_skill_sets(
            plugin_set_names=self._plugin_set_names,
            agent_name=self._agent_name.value
        )
        self._logger = logger.getChild(__name__)
        self._logger.info(
            f"Using skill sets: {[ss.name for ss in self._skill_sets]}"
        )
```

**Step 2: Update run() method to loop over skill sets**

Find the `run()` method and update it to iterate over skill sets, creating separate run IDs:

```python
    def run(self) -> BenchmarkResults:
        """Run the benchmark with all configured skill sets."""
        all_results = BenchmarkResults()

        for skill_set in self._skill_sets:
            # Create run ID with skill set suffix
            skill_set_run_id = f"{self._run_id}__{skill_set.name}"
            self._logger.info(f"Starting run for skill set: {skill_set.name}")

            # Run trials for this skill set
            results = self._run_with_skill_set(skill_set, skill_set_run_id)
            all_results.results.extend(results.results)

        return all_results
```

Add the new method:

```python
    def _run_with_skill_set(self, skill_set: SkillSet, run_id: str) -> BenchmarkResults:
        """Run benchmark trials with a specific skill set."""
        # Store current run_id and restore after
        original_run_id = self._run_id
        self._run_id = run_id
        self._current_skill_set = skill_set

        # Ensure output directory exists
        self._run_path.mkdir(parents=True, exist_ok=True)

        try:
            # Call existing run logic (refactored into _execute_trials)
            return self._execute_trials()
        finally:
            self._run_id = original_run_id
```

**Step 3: Update _create_agent_for_task to remove use_mcp**

Find:
```python
        # Pass use_mcp flag to installed agents
        agent_kwargs["use_mcp"] = self._use_mcp
```

Remove those lines.

**Step 4: Update trial result creation to include skill set metadata**

In the method that creates TrialResults, add:

```python
            skill_set_name=self._current_skill_set.name if hasattr(self, '_current_skill_set') else None,
            skill_set_skills=self._current_skill_set.skills if hasattr(self, '_current_skill_set') else None,
            skill_set_mcp_servers=list(self._current_skill_set.mcp_servers.keys()) if hasattr(self, '_current_skill_set') else None,
```

**Step 5: Commit**

```bash
git add ade_bench/harness.py
git commit -m "feat: update Harness to use skill sets with separate run IDs"
```

---

## Task 9: Update SetupOrchestrator to Call Handlers

**Files:**
- Modify: `ade_bench/setup/setup_orchestrator.py`
- Modify: `ade_bench/setup/agent_setup.py`

**Step 1: Update SetupOrchestrator**

Edit `ade_bench/setup/setup_orchestrator.py`:

1. Add imports:
```python
from ade_bench.models.skill_set import SkillSet
from ade_bench.plugins.skills_handler import SkillsHandler
from ade_bench.plugins.mcp_handler import McpHandler
```

2. Update `__init__` to accept skill_set instead of use_skills:

Find:
```python
    def __init__(self, logger=None, terminal=None, session=None, file_diff_handler=None, trial_handler=None, use_skills=False):
        ...
        self.use_skills = use_skills
```

Replace with:
```python
    def __init__(self, logger=None, terminal=None, session=None, file_diff_handler=None, trial_handler=None, skill_set: SkillSet | None = None):
        ...
        self.skill_set = skill_set
        self._skills_handler = SkillsHandler()
        self._mcp_handler = McpHandler()
```

3. Update `setup_agent_config` call in `setup_task`:

Find:
```python
        setup_agent_config(self.terminal, task_id, self.trial_handler, self.logger, self.use_skills)
```

Replace with:
```python
        setup_agent_config(self.terminal, task_id, self.trial_handler, self.logger)

        # Install skills and configure MCP if skill set specified
        if self.skill_set:
            if self.skill_set.skills:
                log_harness_info(self.logger, task_id, "setup", f"Installing skills...")
                self._skills_handler.install(self.skill_set, self.terminal)
                log_harness_info(self.logger, task_id, "setup", "Skills installed")

            if self.skill_set.mcp_servers:
                log_harness_info(self.logger, task_id, "setup", f"Configuring MCP servers...")
                agent_name = self.trial_handler.agent_name.value
                self._mcp_handler.configure(self.skill_set, agent_name, self.terminal)
                log_harness_info(self.logger, task_id, "setup", "MCP servers configured")
```

**Step 2: Update agent_setup.py**

Edit `ade_bench/setup/agent_setup.py`:

1. Remove `_install_skills_via_cli` function entirely

2. Update `setup_agent_config` signature to remove `use_skills`:

Find:
```python
def setup_agent_config(terminal, task_id: str, trial_handler, logger, use_skills: bool = False) -> None:
```

Replace with:
```python
def setup_agent_config(terminal, task_id: str, trial_handler, logger) -> None:
```

3. Remove the skills installation at the end:

Find and remove:
```python
    # Install skills for any agent type when --use-skills is enabled
    if use_skills:
        _install_skills_via_cli(terminal, trial_handler)
```

**Step 3: Commit**

```bash
git add ade_bench/setup/setup_orchestrator.py ade_bench/setup/agent_setup.py
git commit -m "feat: update SetupOrchestrator to use SkillsHandler and McpHandler"
```

---

## Task 10: Delete Obsolete Files

**Files:**
- Delete: `shared/scripts/setup-dbt-mcp.sh`

**Step 1: Delete the file**

```bash
git rm shared/scripts/setup-dbt-mcp.sh
```

**Step 2: Commit**

```bash
git commit -m "chore: remove obsolete setup-dbt-mcp.sh (logic moved to McpHandler)"
```

---

## Task 11: Update Harness to Pass Skill Set to Orchestrator

**Files:**
- Modify: `ade_bench/harness.py`

**Step 1: Find where SetupOrchestrator is instantiated**

Search for `SetupOrchestrator(` in harness.py and update to pass `skill_set`:

Find patterns like:
```python
SetupOrchestrator(
    logger=...,
    terminal=...,
    session=...,
    file_diff_handler=...,
    trial_handler=...,
    use_skills=self._use_skills
)
```

Replace with:
```python
SetupOrchestrator(
    logger=...,
    terminal=...,
    session=...,
    file_diff_handler=...,
    trial_handler=...,
    skill_set=self._current_skill_set if hasattr(self, '_current_skill_set') else None
)
```

**Step 2: Run integration test**

Run: `uv run ab run simple001 --db duckdb --project-type dbt --agent sage --plugin-set no-plugins`
Expected: Run completes without errors

**Step 3: Commit**

```bash
git add ade_bench/harness.py
git commit -m "feat: pass skill_set to SetupOrchestrator"
```

---

## Task 12: Final Integration Test

**Step 1: Test with defaults (A/B comparison)**

```bash
uv run ab run simple001 --db duckdb --project-type dbt --agent claude
```

Expected: Creates two runs:
- `experiments/<timestamp>__no-plugins/`
- `experiments/<timestamp>__dbt-mcp/`

**Step 2: Test with explicit plugin set**

```bash
uv run ab run simple001 --db duckdb --project-type dbt --agent claude --plugin-set dbt-skills
```

Expected: Creates one run:
- `experiments/<timestamp>__dbt-skills/`

**Step 3: Test incompatible agent error**

```bash
uv run ab run simple001 --db duckdb --project-type dbt --agent gemini --plugin-set dbt-skills
```

Expected: Error message about dbt-skills not being compatible with gemini

**Step 4: Commit final state**

```bash
git add -A
git commit -m "feat: complete plugin sets implementation"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Pydantic models | `ade_bench/models/skill_set.py` |
| 2 | YAML config | `experiment_sets/skill-sets.yaml` |
| 3 | Loader | `ade_bench/plugins/loader.py` |
| 4 | SkillsHandler | `ade_bench/plugins/skills_handler.py` |
| 5 | McpHandler | `ade_bench/plugins/mcp_handler.py` |
| 6 | Update models | `ade_bench/harness_models.py` |
| 7 | Update CLI | `ade_bench/cli/ab/main.py` |
| 8 | Update Harness | `ade_bench/harness.py` |
| 9 | Update Orchestrator | `ade_bench/setup/setup_orchestrator.py` |
| 10 | Delete obsolete | `shared/scripts/setup-dbt-mcp.sh` |
| 11 | Wire up Harness | `ade_bench/harness.py` |
| 12 | Integration test | Manual verification |
