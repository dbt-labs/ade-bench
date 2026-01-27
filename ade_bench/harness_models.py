"""Data models for ADE-Bench harness."""
import uuid

from enum import Enum
from typing import Any, List, Optional
from pathlib import Path
import yaml
import numpy as np
from collections import defaultdict

from pydantic import BaseModel, Field, computed_field
from ade_bench.parsers.base_parser import UnitTestStatus


class FailureMode(Enum):
    UNSET = "unset"
    NONE = "none"
    UNKNOWN = "unknown"
    SETUP_FAILED = "setup_failed"
    SETUP_TIMEOUT = "setup_timeout"
    AGENT_SETUP_TIMEOUT = "agent_setup_timeout"
    AGENT_TIMEOUT = "agent_timeout"
    TEST_TIMEOUT = "test_timeout"
    UNKNOWN_AGENT_ERROR = "unknown_agent_error"
    UNKNOWN_HARNESS_ERROR = "unknown_harness_error"
    HARNESS_PANIC = "harness_panic"  # dbt-fusion or other tool panicked during test execution
    PARSE_ERROR = "parse_error"
    FATAL_LLM_PARSE_ERROR = "fatal_llm_parse_error"
    CONTEXT_LENGTH_EXCEEDED = "context_length_exceeded"
    QUOTA_EXCEEDED = "quota_exceeded"  # API quota/rate limit exceeded
    BREAKPOINT = "breakpoint"

    def is_error(self) -> bool:
        """Check if this failure mode is an infrastructure/harness error vs a task failure."""
        return self in {
            FailureMode.SETUP_FAILED,
            FailureMode.SETUP_TIMEOUT,
            FailureMode.AGENT_SETUP_TIMEOUT,
            FailureMode.AGENT_TIMEOUT,
            FailureMode.TEST_TIMEOUT,
            FailureMode.UNKNOWN_AGENT_ERROR,
            FailureMode.UNKNOWN_HARNESS_ERROR,
            FailureMode.HARNESS_PANIC,
            FailureMode.PARSE_ERROR,
            FailureMode.FATAL_LLM_PARSE_ERROR,
            FailureMode.CONTEXT_LENGTH_EXCEEDED,
            FailureMode.QUOTA_EXCEEDED,
        }

class RunMetadata(BaseModel):
    run_id: str
    uuid: str = Field(default_factory=lambda: str(uuid.uuid4()))
    dataset_path: str
    output_path: str
    agent_name: str
    no_rebuild: bool
    cleanup: bool
    log_level: int
    task_ids: list[str] | None = None
    exclude_task_ids: set[str] | None = None
    n_concurrent_trials: int = 4
    n_attempts: int = 1
    max_episodes: int = 50
    dataset_size: int = 0
    accuracy: float | None = None
    model_name: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    commit_hash: str = "unknown"
    username: str = "unknown"
    s3_bucket: str | None = None
    agent_kwargs: dict[str, Any] | None = None
    pass_at_k: dict[int, float | None] | None = None


class TrialResults(BaseModel):
    trial_name: str
    task_id: str
    task_prompt: str
    is_resolved: bool | None = None
    failure_mode: FailureMode = FailureMode.UNSET
    parser_results: dict[str, UnitTestStatus] | None = None
    expected_test_count: int | None = None  # Expected number of tests (excluding dbt_compile)
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_tokens: int | None = None
    num_turns: int | None = None
    runtime_ms: int | None = None
    cost_usd: float | None = None
    uuid: str = Field(default_factory=lambda: str(uuid.uuid4()))
    recording_path: str | None = None
    # Experiment metadata
    agent: str | None = None
    model_name: str | None = None
    db_type: str | None = None
    project_type: str | None = None
    used_mcp: bool | None = None


class BenchmarkResults(BaseModel):
    results: list[TrialResults] = []

    def _get_task_success_counts(self) -> dict[str, list[int]]:
        success_counts = defaultdict(list)

        for result in self.results:
            success_counts[result.task_id].append(1 if result.is_resolved else 0)

        return success_counts

    def _pass_at_k_estimator(self, n: int, c: int, k: int) -> float:
        """Calculates 1 - comb(n - c, k) / comb(n, k)."""
        if n - c < k:
            return 1.0
        return float(1.0 - np.prod(1.0 - k / np.arange(n - c + 1, n + 1)))

    def _calculate_pass_at_k(self, k: int, task_counts: dict[str, list[int]]) -> float:
        passes = []
        for success in task_counts.values():
            if len(success) < k:
                continue

            passes.append(self._pass_at_k_estimator(len(success), sum(success), k))

        return float(np.mean(passes))

    @computed_field
    @property
    def pass_at_k(self) -> dict[int, float | None]:
        """
        Calculate pass@k metrics for different k values.

        For each k, returns the percentage of tasks where at least one attempt was
        correct.
        """
        if not self.results:
            return {}

        task_counts = self._get_task_success_counts()

        min_attempts = min(len(counts) for counts in task_counts.values())
        k_values = sorted({2**i for i in range(1, int(np.log2(min_attempts)) + 1)})

        if min_attempts >= 5:
            k_values.append(5)
        if min_attempts >= 10:
            k_values.append(10)

        return {k: self._calculate_pass_at_k(k, task_counts) for k in k_values}

    @computed_field
    @property
    def n_resolved(self) -> int:
        return len([r for r in self.results if r.is_resolved])

    @computed_field
    @property
    def n_unresolved(self) -> int:
        return len([r for r in self.results if not r.is_resolved])

    @computed_field
    @property
    def resolved_ids(self) -> list[str]:
        return [r.task_id for r in self.results if r.is_resolved]

    @computed_field
    @property
    def unresolved_ids(self) -> list[str]:
        return [r.task_id for r in self.results if not r.is_resolved]

    @computed_field
    @property
    def accuracy(self) -> float:
        if not self.results:
            return 0.0
        return self.n_resolved / len(self.results)


class VariantConfig(BaseModel):
    """Configuration for a task variant."""

    db_type: str = Field(pattern="^(duckdb|sqlite|postgres|snowflake)$")
    db_name: str
    project_type: str = Field(default="dbt", pattern="^(dbt|dbt-fusion)$")
    project_name: str
    migration_directory: Optional[str] = None  # Name of directory in shared/migrations
    project_dir: Optional[str] = None  # Directory containing the dbt project (overrides default projects dir)
    db_dir: Optional[str] = None  # Directory containing the DuckDB database file (overrides default databases dir)




class SolutionSeedConfig(BaseModel):
    """Configuration for a single solution seed."""

    table_name: str
    include_columns: Optional[List[str]] = None
    exclude_columns: Optional[List[str]] = None
    exclude_tests: Optional[List[str]] = None
    alternates: Optional[List[str]] = None


class TaskMetadata(BaseModel):
    """Metadata for a task."""

    task_id: str
    description: str
    prompt: str
    difficulty: str = Field(pattern="^(easy|medium|hard)$")
    tags: List[str] = Field(default_factory=list)
    test_type: str = "sql"
    db_type: str = "duckdb"
    variants: List[VariantConfig] = Field(default_factory=list)

class TerminalCommand(BaseModel):
    command: str
    min_timeout_sec: float = 0.0
    max_timeout_sec: float = 180.0
    block: bool = False
    append_enter: bool = True

    @classmethod
    def from_yaml_list(cls, path: Path) -> list["TerminalCommand"]:
        """Load a list of terminal commands from a YAML file."""
        data = yaml.safe_load(path.read_text())
        return [cls.model_validate(obj) for obj in data]
