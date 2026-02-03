"""
Any agent that implements this abstract class will be installed into the task container
and executed using a shell command.

This is useful for agents that are not compatible with the tools we provide to interact
with the task container externally.

This should be used as a last resort, because it adds unnecessary dependencies to the
task container and may fail due to properties of the task container rather than the
agent's inability to perform the task (e.g. volume constraints, broken networking).
"""

import shlex
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from ade_bench.agents.agent_name import AgentName
from ade_bench.agents.base_agent import AgentResult, BaseAgent
from ade_bench.harness_models import TerminalCommand, FailureMode
from ade_bench.terminal.tmux_session import TmuxSession
from ade_bench.utils.logger import log_harness_info, logger
from ade_bench.config import config


class AbstractInstalledAgent(BaseAgent, ABC):
    NAME = AgentName.ABSTRACT_INSTALLED

    def __init__(self, model_name: str | None = None, allowed_tools: list[str] | None = None, **kwargs):
        super().__init__(**kwargs)
        self._variant_config = {}
        self._model_name = model_name
        self._allowed_tools = allowed_tools or []

    @property
    @abstractmethod
    def _env(self) -> dict[str, str]:
        """
        Environment variables to use when running the agent (e.g. ANTHROPIC_API_KEY).
        """
        ...

    @property
    @abstractmethod
    def _install_agent_script(self) -> Path:
        """
        Script to install the agent in the container.
        """
        ...

    def set_variant_config(self, config: dict) -> None:
        self._variant_config = config

    @abstractmethod
    def _run_agent_commands(self, task_prompt: str) -> list[TerminalCommand]:
        """
        Commands to run the agent with the given task prompt.
        """
        pass

    def _create_env_setup_file(self) -> str:
        return "\n".join(
            [f"export {key}='{value}'" for key, value in self._env.items()]
        )

    def perform_task(
        self,
        task_prompt: str,
        session: TmuxSession,
        logging_dir: Path | None = None,
        task_name: str | None = None,
    ) -> AgentResult:
        # Agent setup phase - catch timeouts here and return with AGENT_SETUP_TIMEOUT
        try:
            session.copy_to_container(
                self._install_agent_script,
                container_dir="/installed-agent",
                container_filename="install-agent.sh",
            )

            # Execute outside the session to avoid exposing the env variables.
            env_setup_content = self._create_env_setup_file()
            session.container.exec_run(
                [
                    "sh",
                    "-c",
                    (
                        f"echo {shlex.quote(env_setup_content)} > "
                        "/installed-agent/setup-env.sh"
                    ),
                ]
            )

            session.send_keys(
                [
                    "source /installed-agent/setup-env.sh",
                    "Enter",
                ],
                block=True,
                max_timeout_sec=config.setup_timeout_sec,  # Use setup timeout for env setup
            )

            session.send_keys(
                [
                    "source /installed-agent/install-agent.sh",
                    "Enter",
                ],
                block=True,
                max_timeout_sec=config.setup_timeout_sec,  # Use setup timeout for installation
            )
        except TimeoutError:
            log_harness_info(
                logger,
                task_name,
                "agent",
                f"Agent setup timed out after {config.setup_timeout_sec}s during setup and installation phase"
            )
            return AgentResult(
                input_tokens=0,
                output_tokens=0,
                cache_tokens=0,
                num_turns=0,
                runtime_ms=0,
                cost_usd=0.0,
                failure_mode=FailureMode.AGENT_SETUP_TIMEOUT,
            )

        # Create a log file for agent output
        agent_output_file = "/tmp/agent_output.log"

        run_agent_commands = self._run_agent_commands(task_prompt)
        for command in run_agent_commands:
            log_harness_info(logger, task_name, "agent", f"Calling agent: {task_prompt.replace(chr(10), ' ').replace(chr(13), '')[:100]}")

            # Redirect output to log file
            modified_command = TerminalCommand(
                command=f"{command.command} 2>&1 | tee {agent_output_file}",
                min_timeout_sec=command.min_timeout_sec,
                max_timeout_sec=command.max_timeout_sec,
                block=command.block,
                append_enter=command.append_enter,
            )
            session.send_command(modified_command)

        log_harness_info(logger, task_name, "agent", "Agent returned response")

        # Read the output from the log file
        output = session.container.exec_run(["cat", agent_output_file]).output.decode("utf-8")

        # Try to extract just the JSON part from the output
        parsed_metrics = self._parse_agent_output(output)

        # Log the agent response metrics if we have a task name
        if parsed_metrics:
            log_harness_info(
                logger,
                task_name,
                "agent",
                f"Agent response: Runtime: {parsed_metrics.get('runtime_ms', 0)/1000}s, "
                f"Cost: ${parsed_metrics.get('cost_usd', 0.0):.4f}, "
                f"Turns: {parsed_metrics.get('num_turns', 0)}, "
                f"Tokens: in-{parsed_metrics.get('input_tokens', 0)} "
                f"out-{parsed_metrics.get('output_tokens', 0)} "
                f"cache-{parsed_metrics.get('cache_tokens', 0)}, "
                f"SUCCESS: {parsed_metrics.get('success', False)}"
            )

        # Map error string to FailureMode
        error = parsed_metrics.get("error")
        failure_mode = FailureMode.NONE
        if error == "quota_exceeded":
            failure_mode = FailureMode.QUOTA_EXCEEDED
            log_harness_info(logger, task_name, "agent", "Quota exceeded error detected")

        return AgentResult(
            input_tokens=parsed_metrics["input_tokens"],
            output_tokens=parsed_metrics["output_tokens"],
            cache_tokens=parsed_metrics["cache_tokens"],
            num_turns=parsed_metrics["num_turns"],
            runtime_ms=parsed_metrics["runtime_ms"],
            cost_usd=parsed_metrics["cost_usd"],
            model_name=parsed_metrics.get("model_name"),
            failure_mode=failure_mode,
        )

    def _parse_agent_output(self, output: str) -> dict[str, Any]:
        """Parse the agent output to extract metrics. Override in subclasses if needed."""
        # Default implementation returns 0 values
        return {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_tokens": 0,
            "num_turns": 0,
            "runtime_ms": 0,
            "cost_usd": 0.0,
        }
