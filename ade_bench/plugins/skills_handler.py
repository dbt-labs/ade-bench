"""Handler for installing skills via Vercel Skills CLI."""

import logging
from ade_bench.models.plugin_set import PluginSet
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

        for repo in plugin_set.skills:
            cmd = f"npx --yes skills add {repo} --all"
            logger.info(f"[SkillsHandler] Installing skills from {repo}...")

            result = terminal.container.exec_run(
                ["sh", "-c", cmd],
                workdir=str(DockerComposeManager.CONTAINER_APP_DIR)
            )

            if result.exit_code != 0:
                logger.warning(
                    f"[SkillsHandler] Skills installation failed for {repo}: "
                    f"{result.output.decode('utf-8')}"
                )
            else:
                logger.info(f"[SkillsHandler] Skills installed successfully from {repo}")
