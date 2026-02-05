from pathlib import Path

from ade_bench.agents.agent_name import AgentName
from ade_bench.agents.base_agent import AgentResult, BaseAgent
from ade_bench.harness_models import FailureMode
from ade_bench.terminal.tmux_session import TmuxSession
from ade_bench.utils.logger import logger


class NoneAgent(BaseAgent):
    NAME = AgentName.NONE

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._logger = logger.getChild(__name__)
        self._variant_config = None

    def perform_task(
        self,
        task_prompt: str,
        session: TmuxSession,
        logging_dir: Path | None = None,
        task_name: str | None = None,
    ) -> AgentResult:
        session.send_keys(["echo $(whoami)", "Enter"], block=True)

        return AgentResult(
            input_tokens=0,
            output_tokens=0,
            cache_tokens=0,
            num_turns=0,
            failure_mode=FailureMode.NONE,
        )
