from pathlib import Path
from typing import Literal, TypedDict

from ade_bench.agents.agent_name import AgentName
from ade_bench.agents.base_agent import AgentResult, BaseAgent
from ade_bench.handlers.trial_handler import TrialHandler
from ade_bench.harness_models import FailureMode, TerminalCommand
from ade_bench.terminal.tmux_session import TmuxSession
from ade_bench.utils.dataset import Dataset
from ade_bench.utils.logger import logger


class ShSolution(TypedDict):
    type: Literal["sh"]
    path: Path


class YamlSolution(TypedDict):
    type: Literal["yaml"]
    commands: list[TerminalCommand]


SolutionDict = dict[str, ShSolution | YamlSolution]


class SageAgent(BaseAgent):
    NAME = AgentName.SAGE

    def __init__(
        self,
        dataset_path: Path,
        task_ids: list[str] | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)

        self._dataset = Dataset(
            dataset_path=dataset_path,
            task_ids=task_ids,
        )

        self._logger = logger.getChild(__name__)
        self._init_solution_dict()
        self._variant_config = None

    def _init_solution_dict(self) -> None:
        solution_dict: SolutionDict = {}
        for task_path, task_key in self._dataset:
            trial_handler = TrialHandler(
                trial_name="sage",
                input_path=task_path,
                task_key=task_key,
            )

            if trial_handler.solution_path.suffix == ".sh":
                solution_dict[trial_handler.task_prompt] = {
                    "type": "sh",
                    "path": trial_handler.solution_path,
                }
            else:
                solution_dict[trial_handler.task_prompt] = {
                    "type": "yaml",
                    "commands": TerminalCommand.from_yaml_list(trial_handler.solution_path),
                }

        self._solution_dict = solution_dict

    def set_variant_config(self, variant_config: dict) -> None:
        """Set the variant configuration for the current task."""
        self._variant_config = variant_config

    def perform_task(
        self,
        task_prompt: str,
        session: TmuxSession,
        logging_dir: Path | None = None,
        task_name: str | None = None,
    ) -> AgentResult:
        solution = self._solution_dict[task_prompt]

        if solution["type"] == "sh":
            # Copy solutions directory if it exists
            solutions_path = solution["path"].parent / "solutions"
            if solutions_path.exists():
                session.copy_to_container(
                    solutions_path,
                    container_dir="/sage/solutions",
                )

            session.copy_to_container(
                solution["path"],
                container_dir="/sage",
                container_filename="solution.sh",
            )
            # Build command with optional parameters
            command = "bash /sage/solution.sh"
            if self._variant_config:
                db_type = self._variant_config.get("db_type")
                project_type = self._variant_config.get("project_type")
                if db_type:
                    command += f" --db-type={db_type}"
                if project_type:
                    command += f" --project-type={project_type}"

            session.send_keys(
                [command, "Enter"],
                max_timeout_sec=float("inf"),
                block=True,
            )
        else:
            for command in solution["commands"]:
                session.send_command(command)

        return AgentResult(
            input_tokens=0,
            output_tokens=0,
            cache_tokens=0,
            num_turns=0,
            failure_mode=FailureMode.NONE,
        )
