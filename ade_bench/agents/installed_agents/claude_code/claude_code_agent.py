import json
import os
import shlex
from pathlib import Path
from typing import Any

from ade_bench.agents.agent_name import AgentName
from ade_bench.agents.installed_agents.abstract_installed_agent import (
    AbstractInstalledAgent,
)
from ade_bench.harness_models import TerminalCommand
from ade_bench.parsers.claude_parser import ClaudeParser
from ade_bench.config import config


class ClaudeCodeAgent(AbstractInstalledAgent):
    NAME = AgentName.CLAUDE_CODE
    ALLOWED_TOOLS = ["Bash", "Edit", "Write", "NotebookEdit", "WebFetch", "mcp__dbt"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._claude_parser = ClaudeParser()

    @property
    def _env(self) -> dict[str, str]:
        return {
            "ANTHROPIC_API_KEY": os.environ["ANTHROPIC_API_KEY"],
        }

    @property
    def _install_agent_script(self) -> os.PathLike:
        return Path(__file__).parent / "claude-code-setup.sh"

    def _is_agent_output_complete(self, container, output_file: str) -> bool:
        """Detect Claude Code completion by checking for the result JSON line."""
        try:
            result = container.exec_run(
                ["bash", "-c", f"tail -20 {output_file}"]
            )
            if result.exit_code != 0:
                return False
            for line in reversed(result.output.decode("utf-8", errors="replace").strip().split("\n")):
                line = line.strip()
                if not line or not line.startswith("{"):
                    continue
                try:
                    data = json.loads(line)
                    if data.get("type") == "result":
                        return True
                except json.JSONDecodeError:
                    continue
            return False
        except Exception:
            return False

    def _run_agent_commands(self, task_prompt: str) -> list[TerminalCommand]:
        header = "echo 'AGENT RESPONSE: ' && "
        escaped_prompt = shlex.quote(task_prompt)
        command = f"{header} claude --output-format json -p {escaped_prompt}"

        if self._model_name:
            command += f" --model {self._model_name}"

        command += f" --allowedTools {' '.join(self.ALLOWED_TOOLS)}"

        return [
            TerminalCommand(
                command=command,
                min_timeout_sec=0.0,
                max_timeout_sec=config.default_agent_timeout_sec,
                block=True,
                append_enter=True,
            )
        ]

    def _parse_agent_output(self, output: str) -> dict[str, Any]:
        """Parse Claude agent output to extract metrics."""
        # The output should now be cleaner since we're using capture_entire=False
        # But let's still try to extract just the JSON part if there's any extra content
        return self._claude_parser.parse(output)
