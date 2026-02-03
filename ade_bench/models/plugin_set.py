"""Pydantic models for plugin set configuration."""

from pydantic import BaseModel


class McpServerConfig(BaseModel):
    """Configuration for an MCP server."""
    command: str
    args: list[str] = []
    env: dict[str, str] = {}


class PluginSet(BaseModel):
    """Configuration for a set of plugins (skills and MCP servers)."""
    name: str
    description: str = ""
    default: bool = False
    agents: list[str] | None = None  # None = all agents compatible
    skills: list[str] = []
    mcp_servers: dict[str, McpServerConfig] = {}
    allowed_tools: list[str] = []

    def is_compatible_with_agent(self, agent_name: str) -> bool:
        """Check if this plugin set is compatible with the given agent."""
        if self.agents is None:
            return True
        return agent_name in self.agents


class PluginSetsConfig(BaseModel):
    """Root configuration containing all plugin sets."""
    sets: list[PluginSet]

    def get_defaults(self) -> list[PluginSet]:
        """Get all plugin sets marked as default."""
        return [s for s in self.sets if s.default]

    def get_by_name(self, name: str) -> PluginSet | None:
        """Get a plugin set by name."""
        for s in self.sets:
            if s.name == name:
                return s
        return None

    def get_by_names(self, names: list[str]) -> list[PluginSet]:
        """Get multiple plugin sets by name. Raises if any not found."""
        result = []
        for name in names:
            plugin_set = self.get_by_name(name)
            if plugin_set is None:
                available = [s.name for s in self.sets]
                raise ValueError(
                    f"Unknown plugin set '{name}'. Available: {', '.join(available)}"
                )
            result.append(plugin_set)
        return result
