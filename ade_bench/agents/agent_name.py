from enum import Enum


class AgentName(Enum):
    # Abstract agents
    ABSTRACT_INSTALLED = "abstract-installed"

    # Non-abstract agents
    NONE = "none"
    SAGE = "sage"
    CLAUDE_CODE = "claude"
    OPENAI_CODEX = "codex"
    DEEP_AGENTS_CODE = "dcode"
    GEMINI_CLI = "gemini"
    MACRO = "macro"

    def model_name_from_agent_name(model_name, agent_name):
        if agent_name == AgentName.SAGE:
            return "Sage"
        elif agent_name == AgentName.NONE:
            return "None"
        else:
            return model_name
