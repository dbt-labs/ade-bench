from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar, Optional

from pydantic import BaseModel, Field

from ade_bench.agents.agent_name import AgentName
from ade_bench.harness_models import FailureMode
from ade_bench.terminal.tmux_session import TmuxSession


class RequireNameMeta(type(ABC)):
    def __init__(cls, name, bases, dct):
        super().__init__(name, bases, dct)

        if name != "BaseAgent" and not hasattr(cls, "NAME"):
            raise TypeError(f"Class {name} must define a class property 'NAME'.")


class AgentResult(BaseModel):
    input_tokens: int = Field(
        description="The number of input tokens used by the agent to "
        "complete the task."
    )
    output_tokens: int = Field(
        description="The number of output tokens used by the agent to "
        "complete the task."
    )
    cache_tokens: int = Field(
        default=0,
        description="The number of cache tokens used by the agent to "
        "complete the task."
    )
    num_turns: int = Field(
        default=0,
        description="The number of turns in the conversation."
    )
    runtime_ms: int = Field(
        default=0,
        description="The runtime of the agent in milliseconds."
    )
    cost_usd: float = Field(
        default=0.0,
        description="The cost of the agent execution in USD."
    )
    model_name: str | None = Field(
        default=None,
        description="The model name used by the agent, extracted from agent output."
    )
    failure_mode: FailureMode = Field(
        default=FailureMode.NONE,
        description="The failure mode of the agent's execution, if any.",
    )
    timestamped_markers: list[tuple[float, str]] = Field(
        default=[],
        description=(
            "A list of timestamped markers from the agent's execution of the task. "
            "Each marker is a tuple of (timestamp, marker_text). The timestamp is "
            "the time in seconds since the start of the task, and the marker_text is "
            "the text of the marker. The timestamp can be found by calling "
            "`get_asciinema_timestamp()` on the `TmuxSession` object."
        ),
    )


class BaseAgent(ABC, metaclass=RequireNameMeta):
    NAME: ClassVar[AgentName]

    def __init__(self, **kwargs):
        super().__init__()

    def _get_network_name(self, container_name: str) -> str:
        return f"{container_name}__mcp-network"

    def format_agent_log(self, log_path: Path) -> str | None:
        """
        Format the agent's log file into a human-readable string.

        This method can be overridden by subclasses to provide agent-specific
        log formatting. The default implementation returns None, indicating
        that no formatting is available.

        Args:
            log_path: Path to the raw agent log file

        Returns:
            Formatted log content as a string, or None if not available
        """
        return None

    def extract_tools_used(self, log_path: Path) -> list[str] | None:
        """
        Extract deduplicated list of tool names from the agent's log file.

        This method can be overridden by subclasses to provide agent-specific
        tool extraction. The default implementation returns None.

        Args:
            log_path: Path to the raw agent log file

        Returns:
            Sorted list of unique tool names, or None if not available
        """
        return None

    @abstractmethod
    def perform_task(
        self,
        task_prompt: str,
        session: TmuxSession,
        logging_dir: Path | None = None,
        task_name: str | None = None,
    ) -> AgentResult:
        raise NotImplementedError("Agents must implement this method.")
