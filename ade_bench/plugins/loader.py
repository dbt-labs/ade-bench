"""Loader for skill set configuration."""

from pathlib import Path
import yaml

from ade_bench.models.skill_set import SkillSet, SkillSetsConfig


class SkillSetLoader:
    """Loads and resolves skill sets from YAML configuration."""

    def __init__(self, config_path: Path):
        self._config_path = config_path
        self._config: SkillSetsConfig | None = None

    def load(self) -> SkillSetsConfig:
        """Load the skill sets configuration from YAML."""
        if not self._config_path.exists():
            raise FileNotFoundError(f"Skill sets config not found: {self._config_path}")

        with open(self._config_path) as f:
            data = yaml.safe_load(f)

        self._config = SkillSetsConfig(**data)
        return self._config

    def resolve_skill_sets(
        self,
        plugin_set_names: list[str] | None,
        agent_name: str,
    ) -> list[SkillSet]:
        """Resolve which skill sets to use for a run.

        Args:
            plugin_set_names: Explicit skill set names from --plugin-set, or None for defaults
            agent_name: The agent being used (e.g., "claude", "gemini")

        Returns:
            List of SkillSet objects to use

        Raises:
            ValueError: If requested skill set is not found or incompatible
        """
        if self._config is None:
            self.load()

        # Get skill sets (explicit or defaults)
        if plugin_set_names:
            skill_sets = self._config.get_by_names(plugin_set_names)
            # Validate all are compatible with agent
            for ss in skill_sets:
                if not ss.is_compatible_with_agent(agent_name):
                    raise ValueError(
                        f"Skill set '{ss.name}' is not compatible with agent '{agent_name}'. "
                        f"Compatible agents: {ss.agents}"
                    )
        else:
            skill_sets = self._config.get_defaults()

        # Filter to compatible skill sets
        compatible = [ss for ss in skill_sets if ss.is_compatible_with_agent(agent_name)]

        if not compatible:
            if plugin_set_names:
                raise ValueError(
                    f"No compatible skill sets found for agent '{agent_name}' "
                    f"from requested: {plugin_set_names}"
                )
            else:
                raise ValueError(
                    f"No compatible skill sets found for agent '{agent_name}'. "
                    f"No default skill sets are compatible with this agent."
                )

        return compatible
