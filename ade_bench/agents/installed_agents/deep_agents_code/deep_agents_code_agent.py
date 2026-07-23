import json
import os
import re
import shlex
from pathlib import Path
from typing import Any

from ade_bench.agents.agent_name import AgentName
from ade_bench.agents.installed_agents.abstract_installed_agent import (
    AbstractInstalledAgent,
)
from ade_bench.config import config
from ade_bench.harness_models import TerminalCommand


class DeepAgentsCodeAgent(AbstractInstalledAgent):
    """Run LangChain's Deep Agents Code CLI inside an ADE-Bench task container."""

    NAME = AgentName.DEEP_AGENTS_CODE
    _REASONING_EFFORT_ENV_VAR = "DEEPAGENTS_CODE_REASONING_EFFORT"
    _PROVIDER_ENV_VARS = (
        "ANTHROPIC_API_KEY",
        "GOOGLE_API_KEY",
        "GOOGLE_CLOUD_PROJECT",
        "OPENAI_API_KEY",
    )
    _USAGE_ROW = re.compile(
        r"^\s*\S+\s+\S+\s+(?P<requests>\d+)\s+"
        r"(?P<input>[\d.]+[KMB]?)\s+(?P<output>[\d.]+[KMB]?)\s*$",
        re.MULTILINE,
    )

    @property
    def _env(self) -> dict[str, str]:
        return {name: value for name in self._PROVIDER_ENV_VARS if (value := os.environ.get(name))}

    @property
    def _install_agent_script(self) -> Path:
        return Path(__file__).parent / "deep_agents_code-setup.sh"

    def _run_agent_commands(self, task_prompt: str) -> list[TerminalCommand]:
        command_parts = [
            "echo 'AGENT RESPONSE: '",
            "dcode",
            "--no-mcp",
            "--no-stream",
            "--shell-allow-list all",
        ]

        if self._model_name:
            command_parts.append(f"--model {shlex.quote(self._model_name)}")

        if effort := os.environ.get(self._REASONING_EFFORT_ENV_VAR):
            model_params = json.dumps({"reasoning": {"effort": effort}})
            command_parts.append(f"--model-params {shlex.quote(model_params)}")

        command_parts.append(f"--non-interactive {shlex.quote(task_prompt)}")
        command = " && ".join(command_parts[:2]) + " " + " ".join(command_parts[2:])

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
        # dcode prints a human-readable Usage Stats table after successful
        # non-interactive runs. Its compact K/M/B values are rounded by dcode,
        # so the parsed token counts are approximate rather than exact.
        usage_output = output.partition("Usage Stats")[2]
        usage_match = self._USAGE_ROW.search(usage_output)
        input_tokens = 0
        output_tokens = 0
        num_turns = 0
        if usage_match:
            input_tokens = self._parse_compact_token_count(usage_match["input"])
            output_tokens = self._parse_compact_token_count(usage_match["output"])
            num_turns = int(usage_match["requests"])

        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_tokens": 0,
            "num_turns": num_turns,
            "runtime_ms": 0,
            "cost_usd": 0.0,
            "model_name": self._model_name,
        }

    @staticmethod
    def _parse_compact_token_count(value: str) -> int:
        multiplier = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}
        suffix = value[-1]
        if suffix in multiplier:
            return round(float(value[:-1]) * multiplier[suffix])
        return int(value)
