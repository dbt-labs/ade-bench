"""Handler for installing skills via Vercel Skills CLI."""

import logging
from ade_bench.harness_models import PluginSet, SkillOrigin
from ade_bench.terminal.docker_compose_manager import DockerComposeManager

logger = logging.getLogger(__name__)


class SkillsHandler:
    """Installs skills from plugin set configuration."""

    def install(self, plugin_set: PluginSet, terminal: DockerComposeManager) -> None:
        """Install skills from the plugin set into the container.

        Args:
            plugin_set: The plugin set configuration
            terminal: The Docker container manager
        """
        if not plugin_set.skills:
            logger.debug(f"[SkillsHandler] No skills to install for '{plugin_set.name}'")
            return

        for skill_origin in plugin_set.skills:
            self._install_skill_origin(skill_origin, terminal)

    def _install_skill_origin(
        self, skill_origin: SkillOrigin, terminal: DockerComposeManager
    ) -> None:
        """Install skills from a single skill origin.

        Args:
            skill_origin: The skill origin configuration
            terminal: The Docker container manager
        """
        # Base command with non-interactive flags:
        # -y: skip confirmation prompts
        # -g: install globally (to ~/.agents/skills)
        base_cmd = f"npx --yes skills add {skill_origin.location} -y -g"

        if skill_origin.install_all():
            cmd = f"{base_cmd} --all"
            desc = f"all skills from {skill_origin.location}"
        else:
            # Use --skill flag for each skill name (per npx skills CLI syntax)
            skill_flags = " ".join(f"--skill {name}" for name in skill_origin.skill_names)
            cmd = f"{base_cmd} {skill_flags}"
            desc = f"skills {skill_origin.skill_names} from {skill_origin.location}"

        logger.info(f"[SkillsHandler] Installing {desc}...")

        result = terminal.container.exec_run(
            ["sh", "-c", cmd],
            workdir=str(DockerComposeManager.CONTAINER_APP_DIR)
        )

        if result.exit_code != 0:
            logger.warning(
                f"[SkillsHandler] Skills installation failed for {skill_origin.location}: "
                f"{result.output.decode('utf-8')}"
            )
        else:
            logger.info(f"[SkillsHandler] Successfully installed {desc}")
