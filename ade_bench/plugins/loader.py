"""Loader for plugin set configuration."""

from pathlib import Path
import yaml

from ade_bench.harness_models import PluginSet, PluginSetsConfig


class PluginSetLoader:
    """Loads and resolves plugin sets from YAML configuration."""

    def __init__(self, config_path: Path):
        self._config_path = config_path
        self._config: PluginSetsConfig | None = None

    def load(self) -> PluginSetsConfig:
        """Load the plugin sets configuration from YAML."""
        if not self._config_path.exists():
            raise FileNotFoundError(f"Plugin sets config not found: {self._config_path}")

        with open(self._config_path) as f:
            data = yaml.safe_load(f)

        self._config = PluginSetsConfig(**data)
        return self._config

    def resolve_plugin_sets(
        self,
        plugin_set_names: list[str] | None,
        agent_name: str,
    ) -> list[PluginSet]:
        """Resolve which plugin sets to use for a run.

        Args:
            plugin_set_names: Explicit plugin set names from --plugin-set, or None for defaults
            agent_name: The agent being used (e.g., "claude", "gemini")

        Returns:
            List of PluginSet objects to use

        Raises:
            ValueError: If requested plugin set is not found or incompatible
        """
        if self._config is None:
            self.load()

        # Get plugin sets (explicit or defaults)
        if plugin_set_names:
            plugin_sets = self._config.get_by_names(plugin_set_names)
            # Validate all are compatible with agent
            for ps in plugin_sets:
                if not ps.is_compatible_with_agent(agent_name):
                    raise ValueError(
                        f"Plugin set '{ps.name}' is not compatible with agent '{agent_name}'. "
                        f"Compatible agents: {ps.agents}"
                    )
        else:
            plugin_sets = self._config.get_defaults()

        # Filter to compatible plugin sets
        compatible = [ps for ps in plugin_sets if ps.is_compatible_with_agent(agent_name)]

        if not compatible:
            if plugin_set_names:
                raise ValueError(
                    f"No compatible plugin sets found for agent '{agent_name}' "
                    f"from requested: {plugin_set_names}"
                )
            else:
                raise ValueError(
                    f"No compatible plugin sets found for agent '{agent_name}'. "
                    f"No default plugin sets are compatible with this agent."
                )

        return compatible
