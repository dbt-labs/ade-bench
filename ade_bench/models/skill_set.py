"""Pydantic models for skill set configuration."""

from pydantic import BaseModel


class McpServerConfig(BaseModel):
    """Configuration for an MCP server."""
    command: str
    args: list[str] = []
    env: dict[str, str] = {}


class SkillSet(BaseModel):
    """Configuration for a set of skills and tools."""
    name: str
    description: str = ""
    default: bool = False
    agents: list[str] | None = None  # None = all agents compatible
    skills: list[str] = []
    mcp_servers: dict[str, McpServerConfig] = {}
    allowed_tools: list[str] = []

    def is_compatible_with_agent(self, agent_name: str) -> bool:
        """Check if this skill set is compatible with the given agent."""
        if self.agents is None:
            return True
        return agent_name in self.agents


class SkillSetsConfig(BaseModel):
    """Root configuration containing all skill sets."""
    sets: list[SkillSet]

    def get_defaults(self) -> list[SkillSet]:
        """Get all skill sets marked as default."""
        return [s for s in self.sets if s.default]

    def get_by_name(self, name: str) -> SkillSet | None:
        """Get a skill set by name."""
        for s in self.sets:
            if s.name == name:
                return s
        return None

    def get_by_names(self, names: list[str]) -> list[SkillSet]:
        """Get multiple skill sets by name. Raises if any not found."""
        result = []
        for name in names:
            skill_set = self.get_by_name(name)
            if skill_set is None:
                available = [s.name for s in self.sets]
                raise ValueError(
                    f"Unknown skill set '{name}'. Available: {', '.join(available)}"
                )
            result.append(skill_set)
        return result
