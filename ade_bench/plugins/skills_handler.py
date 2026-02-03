"""Handler for installing skills via Vercel Skills CLI."""

import logging
from ade_bench.models.skill_set import SkillSet
from ade_bench.terminal.docker_compose_manager import DockerComposeManager

logger = logging.getLogger(__name__)


class SkillsHandler:
    """Installs skills from skill set configuration."""

    def install(self, skill_set: SkillSet, terminal: DockerComposeManager) -> None:
        """Install skills from the skill set into the container.

        Args:
            skill_set: The skill set configuration
            terminal: The Docker container manager
        """
        if not skill_set.skills:
            logger.debug(f"[SkillsHandler] No skills to install for '{skill_set.name}'")
            return

        for repo in skill_set.skills:
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
