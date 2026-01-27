import json
import os
import subprocess
from enum import Enum
from importlib.resources import files
from pathlib import Path

import yaml
from pydantic import BaseModel, Field
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import LiteralScalarString

from ade_bench.parsers.parser_factory import ParserFactory
from ade_bench.utils.logger import logger
from ade_bench.harness_models import SolutionSeedConfig, VariantConfig
from ade_bench.config import config

# Default directories - can be overridden via environment variables
_PACKAGE_ROOT = Path(str(files("ade_bench"))).parent
DEFAULT_DATABASES_DIR = Path(os.environ.get("ADE_DATABASES_DIR", _PACKAGE_ROOT / "shared" / "databases"))
DEFAULT_PROJECTS_DIR = Path(os.environ.get("ADE_PROJECTS_DIR", _PACKAGE_ROOT / "shared" / "projects"))


class TaskPrompt(BaseModel):
    key: str = Field(
        default="base",
        description=(
            "Use this key to provide various task difficulties based on the task "
            "prompt. Every task must have at least one prompt with the key "
            "'base'."
        ),
    )
    prompt: str


class TaskDifficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    UNKNOWN = "unknown"

    @classmethod
    def choices(cls) -> set[str]:
        return {difficulty.value for difficulty in cls if difficulty != cls.UNKNOWN}

    @classmethod
    def options_str(cls) -> str:
        return ", ".join((cls.EASY, cls.MEDIUM, cls.HARD))


class Task(BaseModel):
    prompts: list[TaskPrompt]

    # Metadata
    author_name: str
    author_email: str
    difficulty: TaskDifficulty
    tags: list[str] = Field(
        default=[],
        description="Tags that describe the type of task this is. Reference other "
        "tasks to see examples.",
    )

    # Configuration
    max_agent_timeout_sec: float = Field(
        default_factory=lambda: config.default_agent_timeout_sec,
        description="Maximum timeout in seconds for the agent to run."
    )
    max_test_timeout_sec: float = Field(
        default_factory=lambda: config.default_test_timeout_sec,
        description="Maximum timeout in seconds for each individual test"
    )
    test_scripts: list[str] = Field(
        default=["setup-dbt-test.sh", "run-dbt-test.sh", "seed-schema.sh", "merge_yaml.py", "run_sql.py", "run_sql.sh"],
        description="List of test scripts to use for the task",
    )
    run_tests_in_same_shell: bool = Field(
        default=False,
        description="Run the tests in the same shell as the agent. This is useful if "
        "you need to test shell-scoped attributes.",
    )
    env_name: str | None = Field(
        default=None,
        description="Instead of providing a Dockerfile and dependencies in the task, "
        "you can provide an environment name. This will use the environment with the "
        "given name from the shared environment directory.",
    )
    variants: list[VariantConfig] = Field(
        default_factory=list,
        description="List of variants for the task. Each variant specifies database and project configurations.",
    )
    solution_seeds: list[str | dict] = Field(
        default=[],
        description="List of solution seeds. Can be table names (strings) or configurations (dicts) with table_name and optional include_columns/exclude_columns.",
    )
    test_setup: str | None = Field(
        default=None,
        description="Optional multiline bash script to run before dbt tests. This script will be executed in the test environment prior to running tests.",
    )
    file_diff_exclude_paths: list[str] | None = Field(
        default=None,
        description="List of path patterns to exclude from file diffing for this task. Overrides global config.",
    )

    @property
    def task_prompt_dict(self) -> dict[str, str]:
        return {task.key: task.prompt for task in self.prompts}

    def get_solution_seed_configs(self) -> list[SolutionSeedConfig]:
        """Parse solution_seeds into SolutionSeedConfig objects."""
        configs = []
        for item in self.solution_seeds:
            if isinstance(item, str):
                # Simple table name
                configs.append(SolutionSeedConfig(table_name=item))
            elif isinstance(item, dict):
                # Configuration dict
                configs.append(SolutionSeedConfig.model_validate(item))
            else:
                raise ValueError(f"Invalid solution_seed item: {item}")
        return configs

    @classmethod
    def from_yaml(cls, path: Path) -> "Task":
        data = yaml.safe_load(path.read_text())
        try:
            return cls.model_validate(data)
        except:
            print("Error validating task", path)
            raise

    def to_yaml(self, path: Path, canary_string: str | None = None) -> None:
        yaml = YAML()
        yaml.indent(mapping=2, sequence=4, offset=2)
        yaml.preserve_quotes = True
        yaml.width = 4096  # Prevent line wrapping
        yaml.default_flow_style = False

        # Convert to JSON and back to dict to ensure all values are serializable
        task_dict = json.loads(self.model_dump_json())

        for prompt in task_dict["prompts"]:
            prompt["prompt"] = LiteralScalarString(prompt["prompt"])

        with open(path, "w") as f:
            if canary_string is not None:
                f.write(canary_string)
            yaml.dump(task_dict, f)

    @property
    def test_script_paths(self) -> list[Path]:
        return [
            Path(str(files("ade_bench"))) / "../shared/scripts" / script_name
            for script_name in self.test_scripts
        ]


class TrialHandler:
    def __init__(
        self,
        trial_name: str,
        input_path: Path,
        output_path: Path | None = None,
        task_key: str = "base",
        variant_config: dict | None = None,
        agent_name = None,
    ):
        self.trial_name = trial_name
        self.input_path = input_path
        self.output_path = output_path
        self.task_key = task_key
        self.variant_config = variant_config or {}
        self.agent_name = agent_name

        self._logger = logger.getChild(__name__)
        self.task = Task.from_yaml(self._task_config_path)

        # Determine parser from variant_config project_type instead of task.parser_name
        project_type = self.variant_config.get("project_type", "dbt")  # Default to dbt
        self.parser = ParserFactory.get_parser(project_type, task_name=self.task_id)

        if self.output_path is not None:
            self._task_output_path.mkdir(parents=True, exist_ok=True)
            self._panes_path.mkdir(parents=True, exist_ok=True)
            self.sessions_path.mkdir(parents=True, exist_ok=True)
            self.agent_logging_dir.mkdir(parents=True, exist_ok=True)

    @property
    def task_id(self) -> str:
        if self.task_key != "base":
            return f"{self.input_path.name}.{self.task_key}"
        return self.input_path.name

    @property
    def _task_config_path(self) -> Path:
        return self.input_path / "task.yaml"

    @property
    def task_prompt(self) -> str:
        if self.task_key not in self.task.task_prompt_dict:
            available_keys = ", ".join(self.task.task_prompt_dict.keys())
            raise ValueError(
                f"Task key '{self.task_key}' not found in {self._task_config_path}. "
                f"Available keys are: {available_keys}. "
                "Please check the task key and ensure it is correctly specified in the "
                "YAML file."
            )

        return self.task.task_prompt_dict[self.task_key]

    @property
    def docker_image_prefix(self) -> str:
        if self.task.env_name is not None:
            return f"ade-bench__env__{self.task.env_name}"
        return f"ade-bench__{self.task_id}".replace(".", "-")

    @property
    def client_container_name(self) -> str:
        return f"{self.trial_name}__client".replace(".", "-")

    @property
    def client_image_name(self) -> str:
        return f"{self.docker_image_prefix}__client"

    def _get_repo_root(self) -> Path:
        """Get the git repository root directory.

        This handles both regular repos and worktrees by finding the actual
        repository root, not the worktree location.
        """
        try:
            # Try to find the git directory first
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=Path(__file__).parent,
                capture_output=True,
                text=True,
                check=True
            )
            git_dir = Path(result.stdout.strip())

            # If git_dir is relative, make it absolute
            if not git_dir.is_absolute():
                git_dir = (Path(__file__).parent / git_dir).resolve()

            # For worktrees, .git is a file pointing to the actual git dir
            # The main repo's .git directory is at <main-repo>/.git
            # For worktrees, git dir is <main-repo>/.git/worktrees/<name>
            if git_dir.name == "worktrees" or "worktrees" in git_dir.parts:
                # This is a worktree, find the main git dir
                # Go up from .git/worktrees/<name> to .git
                while git_dir.name != ".git" and git_dir.parent != git_dir:
                    git_dir = git_dir.parent
                # Now git_dir is the main .git directory
                return git_dir.parent
            else:
                # Regular repo, git_dir is .git directory
                return git_dir.parent

        except subprocess.CalledProcessError:
            # Fallback to package location if not in a git repo
            return Path(str(files("ade_bench"))) / ".."

    @property
    def _shared_path(self) -> Path:
        return Path(str(files("ade_bench"))) / "../shared"

    @property
    def _defaults_path(self) -> Path:
        return self._shared_path / "defaults"

    @property
    def _default_docker_compose_path(self) -> Path:
        return self._defaults_path / "docker-compose.yaml"

    @property
    def _default_run_tests_path(self) -> Path:
        return self._defaults_path / "run-tests.sh"

    @property
    def docker_compose_path(self) -> Path:
        if self.task.env_name is not None:
            return (
                self._shared_path
                / "environments"
                / self.task.env_name
                / "docker-compose.yaml"
            )

        task_docker_compose_path = self.input_path / "docker-compose.yaml"

        if task_docker_compose_path.exists():
            # Use task-specific docker-compose file if it exists
            return task_docker_compose_path

        else:
            project_type = self.variant_config.get("project_type")
            db_type = self.variant_config.get("db_type")

            # Use database-specific docker-compose file if it exists
            if db_type == "snowflake" and project_type == "dbt-fusion":
                return self._defaults_path / "docker-compose-snowflake-dbtf.yaml"
            elif db_type == "snowflake" and project_type == "dbt":
                return self._defaults_path / "docker-compose-snowflake-dbt.yaml"
            elif db_type == "duckdb":
                return self._defaults_path / "docker-compose-duckdb-dbt.yaml"
            else:
                return self._default_docker_compose_path

    @property
    def solution_path(self) -> Path:
        solution_sh_path = self.input_path / "solution.sh"
        solution_yaml_path = self.input_path / "solution.yaml"

        if solution_sh_path.exists():
            return solution_sh_path

        if solution_yaml_path.exists():
            return solution_yaml_path

        raise FileNotFoundError(
            f"No solution.sh or solution.yaml file found for task {self.task_id}"
        )

    @property
    def test_dir(self) -> Path:
        return self.input_path / "tests"

    @property
    def seeds_dir(self) -> Path:
        return self.input_path / "seeds"

    @property
    def solutions_dir(self) -> Path:
        return self.input_path / "solutions"

    @property
    def run_tests_path(self) -> Path:
        task_run_tests_path = self.input_path / "run-tests.sh"

        if not task_run_tests_path.exists():
            self._logger.debug(
                f"No run-tests.sh file found for task {self.task_id}, using "
                "default run-tests.sh."
            )
            return self._default_run_tests_path

        return task_run_tests_path

    @property
    def _task_output_path(self) -> Path:
        if self.output_path is None:
            raise ValueError("Output path is not set")

        return self.output_path / self.task_id / self.trial_name

    @property
    def sessions_path(self) -> Path:
        return self._task_output_path / "sessions"

    @property
    def _panes_path(self) -> Path:
        return self._task_output_path / "panes"

    @property
    def raw_piped_pane_path(self) -> Path:
        return self._panes_path / "raw-piped.txt"

    @property
    def pre_agent_pane_path(self) -> Path:
        return self._panes_path / "pre-agent.txt"

    @property
    def agent_pane_path(self) -> Path:
        return self._panes_path / "agent.txt"

    @property
    def post_agent_pane_path(self) -> Path:
        return self._panes_path / "post-agent.txt"

    @property
    def commands_path(self) -> Path:
        return self._task_output_path / "commands.txt"

    @property
    def results_path(self) -> Path:
        return self._task_output_path / "results.json"

    @property
    def recording_path(self) -> Path:
        return self._task_output_path / "recording.cast"

    @property
    def agent_logging_dir(self) -> Path:
        return self._task_output_path / "agent-logs"

    # Setup-related path properties
    @property
    def task_setup_script_path(self) -> Path:
        """Path to the task's setup.sh script."""
        return self.input_path / "setup.sh"

    @property
    def task_setup_dir_path(self) -> Path:
        """Path to the task's setup directory."""
        return self.input_path / "setup"

    @property
    def shared_databases_root_path(self) -> Path:
        """Path to the shared databases directory in the main repository root.

        This always points to the main repo's databases, even when running
        from a worktree. Database files are gitignored and should only exist
        in the main repository to avoid duplication.
        """
        return self._get_repo_root() / "shared" / "databases"

    @property
    def shared_databases_path(self) -> Path:
        """Path to the shared databases directory."""
        return self._shared_path / "databases"

    @property
    def shared_duckdb_path(self) -> Path:
        """Path to the shared DuckDB databases directory in the main repository."""
        return self.shared_databases_root_path / "duckdb"

    @property
    def shared_snowflake_path(self) -> Path:
        """Path to the shared Snowflake databases directory in the main repository."""
        return self.shared_databases_root_path / "snowflake"

    @property
    def shared_projects_path(self) -> Path:
        """Path to the shared projects directory."""
        return self._shared_path / "projects"

    @property
    def shared_migrations_path(self) -> Path:
        """Path to the shared migrations directory."""
        return self._shared_path / "migrations"

    @property
    def shared_config_path(self) -> Path:
        """Path to the shared config directory."""
        return self._shared_path / "config"

    @property
    def run_sql_py_path(self) -> Path:
        """Path to the run_sql.py utility script."""
        return self._shared_path / "scripts" / "run_sql.py"

    @property
    def run_sql_sh_path(self) -> Path:
        """Path to the run_sql.sh utility script."""
        return self._shared_path / "scripts" / "run_sql.sh"

    def get_duckdb_file_path(self, db_name: str, db_dir: str | None = None) -> Path:
        """Get the path to a specific DuckDB database file.

        Args:
            db_name: Name of the database file (without .duckdb extension)
            db_dir: Optional directory containing the database file (overrides default)

        Returns:
            Path to the DuckDB database file
        """
        if db_dir is not None:
            base_dir = Path(db_dir)
        else:
            base_dir = DEFAULT_DATABASES_DIR / "duckdb"
        return (base_dir / f"{db_name}.duckdb").resolve()

    def get_dbt_project_path(self, project_name: str, project_type: str = "dbt", project_dir: str | None = None) -> Path:
        """Get the path to a specific dbt project directory.

        Args:
            project_name: Name of the project directory
            project_type: Type of project (dbt or dbt-fusion)
            project_dir: Optional directory containing the project (overrides default)

        Returns:
            Path to the dbt project directory
        """
        if project_dir is not None:
            base_dir = Path(project_dir)
        else:
            project_type_path = 'dbt' if project_type == 'dbt-fusion' else project_type
            base_dir = DEFAULT_PROJECTS_DIR / project_type_path
        return (base_dir / project_name).resolve()

    def get_migration_path(self, migration_directory: str) -> Path:
        """Get the path to a specific migration directory."""
        return self.shared_migrations_path / migration_directory

    def get_migration_script_path(self, migration_directory: str) -> Path:
        """Get the path to a specific migration script."""
        return self.get_migration_path(migration_directory) / "migration.sh"
