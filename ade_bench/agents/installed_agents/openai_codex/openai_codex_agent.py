import os
import shlex
from pathlib import Path
from typing import Any

from ade_bench.agents.agent_name import AgentName
from ade_bench.agents.installed_agents.abstract_installed_agent import (
    AbstractInstalledAgent,
)
from ade_bench.harness_models import TerminalCommand
from ade_bench.parsers.codex_parser import CodexParser
from ade_bench.config import config


class OpenAICodexAgent(AbstractInstalledAgent):
    NAME = AgentName.OPENAI_CODEX
    # Codex doesn't seem to have an allowed tools option, but I didn't fully check.
    # ALLOWED_TOOLS = ["Bash", "Edit", "Write", "NotebookEdit", "WebFetch"]

    # Optional env-var override for codex's reasoning effort, useful when
    # comparing codex against another agent at a matched effort level.
    _REASONING_EFFORT_ENV_VAR = "OPENAI_CODEX_REASONING_EFFORT"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._codex_parser = CodexParser()

    @property
    def _env(self) -> dict[str, str]:
        return {
            "OPENAI_API_KEY": os.environ["OPENAI_API_KEY"],
        }

    @property
    def _install_agent_script(self) -> os.PathLike:
        return Path(__file__).parent / "openai_codex-setup.sh"

    def _run_agent_commands(self, task_prompt: str) -> list[TerminalCommand]:
        escaped_prompt = shlex.quote(task_prompt)

        if self._model_name:
            model_command = f" --model {self._model_name}"
        else:
            model_command = ""

        # Optional override of codex's default reasoning effort. Set via env var
        # rather than a constructor kwarg so the existing harness/factory plumbing
        # doesn't need to change to thread it through.
        effort_command = ""
        if effort := os.environ.get(self._REASONING_EFFORT_ENV_VAR):
            effort_command = f" -c {shlex.quote(f'model_reasoning_effort={effort}')}"

        command = (
            f"echo 'AGENT RESPONSE: ' && "
            f"printenv OPENAI_API_KEY | codex login --with-api-key && "
            f"codex --ask-for-approval never{model_command}{effort_command} "
            f"exec "
            f"--json --sandbox danger-full-access --skip-git-repo-check "
            f"{escaped_prompt}"
        )

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
        """Parse Codex agent output to extract metrics."""
        return self._codex_parser.parse(output)
