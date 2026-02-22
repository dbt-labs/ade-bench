"""Task scanner for discovering and filtering ade-bench tasks.

Provides a structured API for loading task metadata from task.yaml files,
with optional filtering by database type, project type, status, and task IDs.
"""

from pathlib import Path

import yaml
from pydantic import BaseModel, field_validator

from ade_bench.handlers.trial_handler import TaskPrompt
from ade_bench.harness_models import SolutionSeedConfig, VariantConfig
from ade_bench.utils.logger import logger


class TaskInfo(BaseModel):
    """Structured metadata for an ade-bench task, loaded from task.yaml."""

    task_id: str
    status: str
    description: str
    prompts: list[TaskPrompt]
    variants: list[VariantConfig]
    difficulty: str | None = None
    tags: list[str] = []
    author_name: str | None = None
    author_email: str | None = None
    test_setup: str | None = None
    notes: str | None = None
    solution_seeds: list[SolutionSeedConfig] = []

    @field_validator("solution_seeds", mode="before")
    @classmethod
    def _normalize_solution_seeds(cls, v: list) -> list:
        """Normalize mixed str/dict solution_seeds from YAML into dicts."""
        normalized = []
        for item in v:
            if isinstance(item, str):
                normalized.append({"table_name": item})
            else:
                normalized.append(item)
        return normalized

    def has_variant(self, db_type: str, project_type: str) -> bool:
        """Check if this task has a variant matching the given db_type and project_type."""
        return any(v.db_type == db_type and v.project_type == project_type for v in self.variants)


class TaskScanner:
    """Scans an ade-bench tasks directory and returns structured task metadata."""

    def __init__(self, tasks_dir: Path):
        """Initialize the scanner.

        Args:
            tasks_dir: Path to the directory containing task subdirectories.
        """
        self._tasks_dir = tasks_dir

    @property
    def tasks_dir(self) -> Path:
        """Return the tasks directory path."""
        return self._tasks_dir

    def scan(
        self,
        task_ids: list[str] | None = None,
        db_type: str | None = None,
        project_type: str | None = None,
        status: str | None = None,
    ) -> list[TaskInfo]:
        """Scan task.yaml files and return matching tasks.

        Args:
            task_ids: Only include tasks whose task_id is in this list.
            db_type: Only include tasks with a variant matching this database type.
            project_type: Only include tasks with a variant matching this project type.
            status: Only include tasks with this status (e.g. "ready").

        Returns:
            List of TaskInfo objects sorted by task_id.
        """
        tasks: list[TaskInfo] = []

        for task_dir in sorted(self._tasks_dir.iterdir()):
            if not task_dir.is_dir() or task_dir.name.startswith("."):
                continue

            task_file = task_dir / "task.yaml"
            if not task_file.exists():
                continue

            try:
                with open(task_file) as f:
                    task_data = yaml.safe_load(f)

                task_info = TaskInfo.model_validate(task_data)

                if task_ids and task_info.task_id not in task_ids:
                    continue

                if status and task_info.status != status:
                    continue

                if db_type or project_type:
                    has_match = any(
                        (db_type is None or v.db_type == db_type)
                        and (project_type is None or v.project_type == project_type)
                        for v in task_info.variants
                    )
                    if not has_match:
                        continue

                tasks.append(task_info)
            except Exception as e:
                logger.warning(f"Failed to load task from {task_file}: {e}")
                continue

        logger.info(f"Scanned {len(tasks)} tasks from {self._tasks_dir}")
        return tasks
