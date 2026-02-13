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

    def __init__(self, use_mcp: bool = False, model_name: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self._variant_config = {}
        self._use_mcp = use_mcp
        self._model_name = model_name

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

    def _is_agent_output_complete(self, container, output_file: str) -> bool:
        """Check if the agent has produced its final output.

        Override in subclasses to enable early termination when the agent
        is done but its process tree hasn't exited (e.g., due to a stuck
        subprocess).

        Returns False by default (rely solely on process exit).
        """
        return False

    def _create_env_setup_file(self) -> str:
        return "\n".join(
            [f"export {key}='{value}'" for key, value in self._env.items()]
        )

    def _get_dbt_dynamic_env(self, session: TmuxSession, task_name: str | None) -> dict[str, str]:
        """Get dynamic environment variables for dbt MCP server."""
        env_vars = {}

        # DBT_PROJECT_DIR is the container app directory
        env_vars["DBT_PROJECT_DIR"] = str(DockerComposeManager.CONTAINER_APP_DIR)

        # Get the dbt path from the container
        result = session.container.exec_run(
            ["sh", "-c", "which dbt"],
            workdir=str(DockerComposeManager.CONTAINER_APP_DIR)
        )
        if result.exit_code == 0:
            dbt_path = result.output.decode("utf-8").strip()
            if dbt_path:
                env_vars["DBT_PATH"] = dbt_path
                log_harness_info(logger, task_name, "agent", f"Found dbt at: {dbt_path}")
        else:
            logger.warning("[MCP] dbt not found in PATH, MCP server may not work correctly")

        # Enable the dbt CLI in dbt-mcp
        env_vars["DISABLE_DBT_CLI"] = "false"

        return env_vars

    def _configure_mcp_servers(self, session: TmuxSession, task_name: str | None) -> None:
        """Configure MCP servers after agent installation."""
        agent_cli = self.NAME.value  # e.g., "claude", "gemini"

        for server_name, mcp_config in self._mcp_servers.items():
            log_harness_info(logger, task_name, "agent", f"Configuring MCP server '{server_name}'...")

            # Start with static env vars from config
            env_vars = dict(mcp_config.env)

            # For dbt MCP server, add dynamic environment variables
            # Check server name or if dbt-mcp appears in any of the args
            is_dbt_mcp = server_name == "dbt" or any("dbt-mcp" in arg for arg in mcp_config.args)
            if is_dbt_mcp:
                dynamic_env = self._get_dbt_dynamic_env(session, task_name)
                # Merge dynamic vars (don't override static config)
                for key, value in dynamic_env.items():
                    if key not in env_vars:
                        env_vars[key] = value

            # Build -e flags for `claude mcp add -e KEY=value` syntax
            env_flags = [f"-e {k}={v}" for k, v in env_vars.items()]
            if env_vars:
                log_harness_info(logger, task_name, "agent", f"Setting env vars: {list(env_vars.keys())}")

            # Build mcp add command (server name before -e to avoid variadic flag consuming it)
            parts = [agent_cli, "mcp", "add", server_name] + env_flags + ["--", mcp_config.command] + mcp_config.args
            mcp_cmd = " ".join(parts)

            result = session.container.exec_run(
                ["sh", "-c", mcp_cmd],
                workdir=str(DockerComposeManager.CONTAINER_APP_DIR)
            )

            if result.exit_code != 0:
                logger.warning(
                    f"[MCP] Server registration failed for {server_name}: "
                    f"{result.output.decode('utf-8')}"
                )
            else:
                log_harness_info(logger, task_name, "agent", f"MCP server '{server_name}' configured")
    def perform_task(
        self,
        task_prompt: str,
        session: TmuxSession,
        logging_dir: Path | None = None,
        task_name: str | None = None,
    ) -> AgentResult:
        """
        Execute the agent task. Agent must be pre-installed in Docker image.

        Args:
            task_prompt: The task prompt to send to the agent
            session: The tmux session to use for execution
            logging_dir: Optional directory for agent logs
            task_name: Optional task name for logging

        Returns:
            AgentResult with metrics and any failure mode
        """
        # Setup env vars (API keys, etc) - still needed at runtime
        try:
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
                max_timeout_sec=config.setup_timeout_sec,
            )

            # Optionally setup dbt MCP server
            if self._use_mcp:
                dbt_mcp_script = Path(__file__).parent.parent.parent.parent / "shared" / "scripts" / "setup-dbt-mcp.sh"
                session.copy_to_container(
                    dbt_mcp_script,
                    container_dir="/scripts",
                    container_filename="setup-dbt-mcp.sh",
                )

                # Pass db_type, project_type, and agent name
                db_type = self._variant_config.get('db_type', 'unknown')
                project_type = self._variant_config.get('project_type', 'unknown')
                agent_name = self.NAME.value if hasattr(self.NAME, 'value') else str(self.NAME)
                session.send_keys(
                    [
                        f"bash /scripts/setup-dbt-mcp.sh {db_type} {project_type} {agent_name}",
                        "Enter",
                    ],
                    block=True,
                    max_timeout_sec=config.setup_timeout_sec,
                )
        except TimeoutError:
            log_harness_info(
                logger,
                task_name,
                "agent",
                f"Agent env setup timed out after {config.setup_timeout_sec}s"
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

        # Agent is pre-installed in Docker image - no installation needed here

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
            completion_check = lambda: self._is_agent_output_complete(
                session.container, agent_output_file
            )
            session.send_command(modified_command, completion_check=completion_check)

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

        return AgentResult(
            input_tokens=parsed_metrics["input_tokens"],
            output_tokens=parsed_metrics["output_tokens"],
            cache_tokens=parsed_metrics["cache_tokens"],
            num_turns=parsed_metrics["num_turns"],
            runtime_ms=parsed_metrics["runtime_ms"],
            cost_usd=parsed_metrics["cost_usd"],
        )

    def _copy_log_file_from_container(self, container, logging_dir: Path) -> str:
        """Read the agent output log from the container and save it locally.

        Args:
            container: Docker container object
            logging_dir: Directory to write the log file to

        Returns:
            The log file content as a string, or empty string on failure
        """
        try:
            result = container.exec_run(["cat", "/tmp/agent_output.log"])
            if result.exit_code != 0:
                return ""
            content = result.output.decode("utf-8")
            (logging_dir / "agent_output.log").write_text(content)
            return content
        except Exception:
            return ""

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
