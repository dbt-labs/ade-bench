"""
Agent-specific setup functions for copying configuration files and other agent resources.
"""

from pathlib import Path
from ..utils.logger import logger
from ..terminal.docker_compose_manager import DockerComposeManager
from ..agents.agent_name import AgentName
from ..utils.logger import log_harness_info


def _copy_config_file(terminal, trial_handler, config_filename: str, container_filename: str = None) -> None:
    """Helper to copy a configuration file to the container."""
    if container_filename is None:
        container_filename = config_filename

    config_path = trial_handler.shared_config_path / config_filename
    if config_path.exists():
        terminal.copy_to_container(
            paths=config_path,
            container_dir=str(DockerComposeManager.CONTAINER_APP_DIR),
            container_filename=container_filename
        )
    else:
        logger.warning(f"Configuration file not found at {config_path}")


def setup_agent_config(terminal, task_id: str, trial_handler, logger) -> None:
    """Setup agent-specific configuration files and resources."""

    agent_name = trial_handler.agent_name

    log_harness_info(logger, task_id, "setup", "Migrating agent config files...")

    # Copy agent-specific config files
    if agent_name == AgentName.CLAUDE_CODE:
        _copy_config_file(terminal, trial_handler, "CLAUDE.md")
    elif agent_name == AgentName.GEMINI_CLI:
        _copy_config_file(terminal, trial_handler, "GEMINI.md")
    elif agent_name == AgentName.OPENAI_CODEX:
        _copy_config_file(terminal, trial_handler, "AGENTS.md")
    elif agent_name == AgentName.MACRO:
        _copy_config_file(terminal, trial_handler, "MACRO.md")
