"""Centralized timeout management for ADE-Bench."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ade_bench.config import config

if TYPE_CHECKING:
    from ade_bench.handlers.trial_handler import Task


@dataclass
class TimeoutSet:
    """Complete set of timeouts for a task execution."""

    setup: float
    agent_execution: float
    cleanup: float
    test_execution: float

    @property
    def total_agent_operation(self) -> float:
        """Total timeout for entire agent perform_task() operation.

        This includes:
        - Agent setup (installation, env vars, etc.)
        - Agent execution (actual task work)
        - Agent cleanup (parsing output, copying logs)
        """
        return self.setup + self.agent_execution + self.cleanup

    @property
    def total_test_operation(self) -> float:
        """Total timeout for entire test operation."""
        # Tests might have their own setup/cleanup in the future
        # For now, just the test execution time
        return self.test_execution

    def __str__(self) -> str:
        """Human-readable representation for logging."""
        return (
            f"TimeoutSet(setup={self.setup}s, "
            f"agent={self.agent_execution}s, "
            f"cleanup={self.cleanup}s, "
            f"test={self.test_execution}s, "
            f"total_agent={self.total_agent_operation}s)"
        )


class TimeoutManager:
    """Manages timeout resolution with task-specific overrides.

    This is the single source of truth for timeout resolution in ADE-Bench.
    It eliminates the need to thread timeout values through multiple layers.
    """

    @staticmethod
    def get_default_timeouts() -> TimeoutSet:
        """Get default timeouts when no task context is available."""
        return TimeoutSet(
            setup=config.setup_timeout_sec,
            agent_execution=config.default_agent_timeout_sec,
            cleanup=config.cleanup_timeout_sec,
            test_execution=config.default_test_timeout_sec,
        )

    @staticmethod
    def get_timeouts_for_task(task: "Task") -> TimeoutSet:
        """
        Resolve all timeouts for a task, applying overrides as needed.

        Task-specific overrides take precedence over global config.

        Args:
            task: Task object that may contain timeout overrides

        Returns:
            TimeoutSet with all resolved timeout values
        """
        return TimeoutSet(
            setup=config.setup_timeout_sec,
            agent_execution=(
                task.max_agent_timeout_sec
                if task.max_agent_timeout_sec
                else config.default_agent_timeout_sec
            ),
            cleanup=config.cleanup_timeout_sec,
            test_execution=(
                task.max_test_timeout_sec
                if task.max_test_timeout_sec
                else config.default_test_timeout_sec
            ),
        )
