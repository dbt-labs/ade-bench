from pathlib import Path
from typing import Iterator
import yaml
from ade_bench.utils.logger import logger


class Dataset:
    """A class for loading and iterating over tasks in a dataset."""

    def __init__(
        self,
        dataset_path: Path,
        task_ids: list[str] | None = None,
        excluded_task_ids: set[str] | None = None,
    ):
        """Initialize the dataset.

        Args:
            dataset_path: Path to the dataset directorygs
            task_ids: Optional list of specific task IDs to load
            excluded_task_ids: Optional set of task IDs to exclude
        """
        self._dataset_path = dataset_path
        self._requested_task_ids = task_ids
        self._excluded_task_ids = excluded_task_ids or set()
        self._logger = logger.getChild(__name__)
        self._tasks: dict[str, tuple[Path, str]] = {}

        if self._requested_task_ids:
            # Get specific tasks from the directory
            self._load_specific_tasks()
        else:
            # Get all tasks from directory, filter to only status=ready
            self._load_all_ready_tasks()

        # Apply exclusions
        self._remove_excluded_tasks()

        # Validate that all task paths exist
        for task_path, _ in self._tasks.values():
            if not task_path.exists():
                raise FileNotFoundError(f"Task path {task_path} does not exist")

    def _load_specific_tasks(self) -> None:
        """Load specific tasks from the task_ids."""
        for task_pattern in self._requested_task_ids:
            if task_pattern.startswith('@'):
                # Experiment set pattern - load tasks from experiment set file
                experiment_set_name = task_pattern[1:]  # Remove the '@'
                self._load_experiment_set(experiment_set_name)
            elif task_pattern.endswith('+'):
                # Wildcard pattern - find all tasks that start with the prefix
                prefix = task_pattern[:-1]  # Remove the '+'
                self._load_wildcard_tasks(prefix)
            else:
                # Get task name and key
                if '.' in task_pattern:
                    task_name, task_key = task_pattern.split('.', 1)
                else:
                    task_name, task_key = task_pattern, None

                # Load the task directory
                task_dir = self._dataset_path / task_name
                if not task_dir.exists():
                    raise FileNotFoundError(f"Task directory {task_dir} does not exist")

                # Load this specific task
                self._load_task(task_dir, task_key, only_ready_tasks=False)

    def _load_wildcard_tasks(self, prefix: str) -> None:
        """Load all tasks that start with the given prefix."""
        # Find all task directories that start with the prefix
        for task_dir in self._dataset_path.iterdir():
            if not task_dir.is_dir():
                continue
            if task_dir.name.startswith(prefix):
                # Load this task (all its keys)
                self._load_task(task_dir, requested_key=None, only_ready_tasks=False)

    def _load_experiment_set(self, experiment_set_name: str) -> None:
        """Load tasks from an experiment set file."""
        experiment_sets_dir = self._dataset_path.parent / "experiment_sets"
        experiment_set_file = experiment_sets_dir / f"{experiment_set_name}.yaml"

        if not experiment_set_file.exists():
            raise FileNotFoundError(f"Experiment set file {experiment_set_file} does not exist")

        with open(experiment_set_file) as f:
            experiment_data = yaml.safe_load(f)

        # Get the task_ids from the experiment set
        task_ids = experiment_data.get("task_ids", [])
        if not task_ids:
            raise ValueError(f"No task_ids found in experiment set {experiment_set_name}")

        # Load each task from the experiment set
        for task_id in task_ids:
            if '.' in task_id:
                task_name, task_key = task_id.split('.', 1)
            else:
                task_name, task_key = task_id, None

            # Load the task directory
            task_dir = self._dataset_path / task_name
            if not task_dir.exists():
                raise FileNotFoundError(f"Task directory {task_dir} does not exist")

            # Load this specific task
            self._load_task(task_dir, task_key, only_ready_tasks=False)

    def _load_all_ready_tasks(self) -> None:
        """Load all tasks from directory, filtering to only status=ready."""
        for task_dir in self._dataset_path.iterdir():
            if not task_dir.is_dir():
                continue
            if not (task_dir / "task.yaml").exists():
                continue
            # Load this task (all its keys)
            self._load_task(task_dir, requested_key=None, only_ready_tasks=True)

    def _load_task(
        self,
        task_dir: Path,
        requested_key: str | None = None,
        only_ready_tasks: bool = False,
    ) -> None:
        """Load a single task, applying all filters and key selection logic."""

        task_yaml_path = task_dir / "task.yaml"
        with open(task_yaml_path) as f:
            task_data = yaml.safe_load(f)

        # Only include tasks with status=ready if only_ready_tasks is True
        if only_ready_tasks and task_data.get("status") != "ready":
            return

        # Add tasks based on what was requested
        for prompt in task_data.get("prompts", []):
            # If a specific key was requested, only include that key
            if requested_key is not None and prompt["key"] != requested_key:
                continue

            task_id = f"{task_dir.name}.{prompt['key']}"
            self._tasks[task_id] = (task_dir, prompt["key"])

    def _remove_excluded_tasks(self) -> None:
        """Remove tasks that are in the excluded list."""
        for excluded_task_id in self._excluded_task_ids:
            if excluded_task_id in self._tasks:
                del self._tasks[excluded_task_id]

    def __iter__(self) -> Iterator[tuple[Path, str]]:
        """Iterate over the tasks in the dataset."""
        return iter([self._tasks[task_id] for task_id in sorted(self._tasks.keys())])

    def __len__(self) -> int:
        """Get the number of tasks in the dataset."""
        return len(self._tasks)

    @property
    def tasks(self) -> list[tuple[Path, str]]:
        """Get the list of tasks in the dataset."""
        return [self._tasks[task_id] for task_id in sorted(self._tasks.keys())]

    @property
    def task_ids(self) -> list[str]:
        """Get the list of task IDs in the dataset."""
        return sorted(self._tasks.keys())