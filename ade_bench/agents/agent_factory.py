from abc import ABC, abstractmethod
from typing import ClassVar

from ade_bench.agents.agent_name import AgentName
from ade_bench.agents.base_agent import BaseAgent
from ade_bench.agents.installed_agents.claude_code.claude_code_agent import (
    ClaudeCodeAgent,
)
from ade_bench.agents.installed_agents.gemini_cli.gemini_cli_agent import (
    GeminiCLIAgent,
)
from ade_bench.agents.installed_agents.macro.macro_agent import (
    MacroAgent,
)
from ade_bench.agents.installed_agents.openai_codex.openai_codex_agent import (
    OpenAICodexAgent,
)
from ade_bench.agents.none_agent import NoneAgent
from ade_bench.agents.sage_agent import SageAgent


class AgentFactory(ABC):
    @property
    @abstractmethod
    def agent_name(self) -> AgentName:
        pass

    @abstractmethod
    def get_agent(self, **kwargs) -> BaseAgent:
        pass


class NamedAgentFactory(AgentFactory):
    AGENT_NAME_TO_CLASS: ClassVar[dict[AgentName, type[BaseAgent]]] = {
        NoneAgent.NAME: NoneAgent,
        SageAgent.NAME: SageAgent,
        ClaudeCodeAgent.NAME: ClaudeCodeAgent,
        OpenAICodexAgent.NAME: OpenAICodexAgent,
        GeminiCLIAgent.NAME: GeminiCLIAgent,
        MacroAgent.NAME: MacroAgent,
    }

    def __init__(self, agent_name: AgentName):
        self._agent_name = agent_name

    @property
    def agent_name(self) -> AgentName:
        return self._agent_name

    def get_agent(self, **kwargs) -> BaseAgent:
        agent_class = self.AGENT_NAME_TO_CLASS.get(self.agent_name)

        if agent_class is None:
            raise ValueError(
                f"Unknown agent: {self.agent_name}. "
                f"Available agents: {self.AGENT_NAME_TO_CLASS.keys()}"
            )

        return agent_class(**kwargs)
