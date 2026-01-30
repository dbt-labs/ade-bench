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


def _install_skills_via_cli(terminal, trial_handler) -> None:
    """Install dbt skills using the Vercel Skills CLI.
    
    The CLI automatically detects which agents are available in the container
    and installs skills to the appropriate directories (.claude/skills/, 
    .cursor/skills/, .codex/skills/, etc.).
    """
    skills_repo = "dbt-labs/dbt-agent-skills"
    install_cmd = f"npx --yes skills add {skills_repo} --all"
    
    logger.info(f"Installing skills from {skills_repo} (supports all agent types)...")
    
    result = terminal.container.exec_run(
        ["sh", "-c", install_cmd],
        workdir=str(DockerComposeManager.CONTAINER_APP_DIR)
    )
    
    if result.exit_code != 0:
        logger.warning(f"Skills installation failed: {result.output.decode('utf-8')}")
    else:
        logger.info(f"Skills installed successfully from {skills_repo}")
        
def setup_agent_config(terminal, task_id: str, trial_handler, logger, use_skills: bool = False) -> None:
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
    
    # Install skills for any agent type when --use-skills is enabled
    if use_skills:
        _install_skills_via_cli(terminal, trial_handler)
