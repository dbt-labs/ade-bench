import os
import shlex
from pathlib import Path
from typing import Any

from ade_bench.agents.agent_name import AgentName
from ade_bench.agents.installed_agents.abstract_installed_agent import (
    AbstractInstalledAgent,
)
from ade_bench.agents.installed_agents.claude_code.log_formatter import ClaudeCodeLogFormatter
from ade_bench.harness_models import TerminalCommand
from ade_bench.parsers.claude_parser import ClaudeParser
from ade_bench.config import config


class ClaudeCodeAgent(AbstractInstalledAgent):
    NAME = AgentName.CLAUDE_CODE

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._claude_parser = ClaudeParser()
        self._log_formatter = ClaudeCodeLogFormatter()

    @property
    def _env(self) -> dict[str, str]:
        return {
            "ANTHROPIC_API_KEY": os.environ["ANTHROPIC_API_KEY"],
        }

    @property
    def _install_agent_script(self) -> os.PathLike:
        return Path(__file__).parent / "claude-code-setup.sh"

    def _run_agent_commands(self, task_prompt: str) -> list[TerminalCommand]:
        header = "echo 'AGENT RESPONSE: ' && "
        escaped_prompt = shlex.quote(task_prompt)
        command = f"{header} claude --output-format stream-json --verbose -p {escaped_prompt}"

        if self._model_name:
            command += f" --model {self._model_name}"

        if self._allowed_tools:
            command += f" --allowedTools {' '.join(self._allowed_tools)}"

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

    def format_agent_log(self, log_path: Path) -> str | None:
        """
        Format the Claude Code agent's log file into a human-readable string.

        Also generates an HTML transcript at log_path.parent / "transcript.html"
        using claude-code-transcripts if available.

        Args:
            log_path: Path to the raw agent.log file (JSON-lines format)

        Returns:
            Formatted log content as a string, or None if formatting failed
        """
        # Generate HTML transcript as a single well-known file
        transcript_path = log_path.parent / "transcript.html"
        self._log_formatter.generate_html_transcript(log_path, transcript_path)

        # Return text-formatted log
        return self._log_formatter.format_log(log_path)

    # Generic tools to filter out from tools_used reporting
    _GENERIC_TOOLS = frozenset({
        'Bash', 'Edit', 'Glob', 'Grep', 'Read', 'Write',
        'WebFetch', 'WebSearch', 'Task', 'NotebookEdit',
        'TodoRead', 'TodoWrite',
    })

    def extract_tools_used(self, log_path: Path) -> list[str] | None:
        """
        Extract deduplicated tool names from Claude Code agent logs.

        Filters out generic tools (Bash, Edit, Glob, etc.) and expands
        Skill tool calls to their actual skill names.
        """
        try:
            turns = self._log_formatter.parse_log_file(log_path)
            tool_names = set()
            for turn in turns:
                for tool in turn.get('tools', []):
                    name = tool['name']
                    # Expand Skill tool to actual skill name
                    if name == 'Skill':
                        skill_name = tool.get('input', {}).get('skill')
                        if skill_name:
                            tool_names.add(f"skill:{skill_name}")
                    # Filter out generic tools
                    elif name not in self._GENERIC_TOOLS:
                        tool_names.add(name)
            return sorted(tool_names) if tool_names else None
        except Exception:
            return None
