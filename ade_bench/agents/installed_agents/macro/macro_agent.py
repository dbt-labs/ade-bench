import os
import shlex
from pathlib import Path
from typing import Any
from ade_bench.agents.agent_name import AgentName
from ade_bench.agents.installed_agents.abstract_installed_agent import (
    AbstractInstalledAgent,
)
from ade_bench.harness_models import TerminalCommand
from ade_bench.parsers.parser_factory import ParserFactory, ParserName
from ade_bench.config import config
from ade_bench.utils.logger import logger


class MacroAgent(AbstractInstalledAgent):
    NAME = AgentName.MACRO
    LOG_FILENAME = "logs.jsonl"
    LOG_DIR = "/tmp"

    def __init__(self, additional_args: str = "", model_name: str | None = None, **kwargs):
        super().__init__(model_name=model_name, **kwargs)
        self.additional_args = additional_args
        self._macro_parser = ParserFactory.get_parser(ParserName.MACRO)

    @property
    def _env(self) -> dict[str, str]:
        return {
            "MACRO_PLATFORM_API_KEY": os.environ["MACRO_API_KEY"],
        }

    @property
    def _install_agent_script(self) -> os.PathLike:
        """Use a local or default Macro install script depending on environment."""
        if os.environ.get("MACRO_BINARY_PATH"):
            return Path(__file__).parent / "macro-setup-local.sh"
        return Path(__file__).parent / "macro-setup.sh"

    def _run_agent_commands(self, task_prompt: str) -> list[TerminalCommand]:
        """Return the command(s) that will run the Macro agent inside the container."""
        escaped_prompt = shlex.quote(task_prompt)
        base_command = (
            f"macro -p {escaped_prompt} -e {self.LOG_DIR}/{self.LOG_FILENAME} --output-format=json"
        )

        if self.additional_args:
            logger.info(f"Running macro with additional args: {self.additional_args}")
            command = f"{base_command} {self.additional_args}"
        else:
            command = base_command

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
        """Parse Macro agent output using the Macro parser."""
        return self._macro_parser.parse(output)
