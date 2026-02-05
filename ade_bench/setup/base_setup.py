"""
Base setup functions for copying files and running scripts.
"""

from typing import Dict, Any
from ..utils.logger import logger
from ..terminal.docker_compose_manager import DockerComposeManager


def setup_base_files(terminal, session, task_id: str, variant: Dict[str, Any], trial_handler) -> None:
    """Setup base files - copy setup files and run scripts."""

    setup_script_path = trial_handler.task_setup_script_path
    setup_dir_path = trial_handler.task_setup_dir_path
    run_sql_py_path = trial_handler.run_sql_py_path
    run_sql_sh_path = trial_handler.run_sql_sh_path

    # Copy setup files
    if setup_script_path.exists():
        terminal.copy_to_container(
            paths=setup_script_path,
            container_dir=str(DockerComposeManager.CONTAINER_APP_DIR),
            container_filename="setup.sh"
        )

    if setup_dir_path.exists():
        terminal.copy_to_container(
            paths=setup_dir_path,
            container_dir=str(DockerComposeManager.CONTAINER_SETUP_DIR)
        )

    # Copy run_sql utility scripts early so they're available for setup.sh and solution.sh
    if run_sql_py_path.exists():
        terminal.copy_to_container(
            paths=[trial_handler.run_sql_py_path],
            container_dir=str(DockerComposeManager.CONTAINER_SCRIPTS_DIR),
            container_filename="run_sql.py"
        )
    if run_sql_sh_path.exists():
        terminal.copy_to_container(
            paths=[trial_handler.run_sql_sh_path],
            container_dir=str(DockerComposeManager.CONTAINER_SCRIPTS_DIR),
            container_filename="run_sql.sh"
        )


    # Run setup script and remove it
    if setup_script_path.exists():
        # Build command with optional parameters
        command = f"bash {DockerComposeManager.CONTAINER_APP_DIR}/setup.sh"
        db_type = variant.get("db_type")
        project_type = variant.get("project_type")
        if db_type:
            command += f" --db-type={db_type}"
        if project_type:
            command += f" --project-type={project_type}"

        # Check if we have a session or just direct container access
        if session is not None:
            session.send_keys([command, "Enter"], block=True)
            container = session.container
        else:
            # For interactive mode, execute the command directly on the container
            logger.info(f"Running setup command: {command}")
            terminal.container.exec_run(command)
            container = terminal.container

        # Clean up setup files
        container.exec_run(["rm", f"{DockerComposeManager.CONTAINER_APP_DIR}/setup.sh"])
        container.exec_run(["rm", "-rf", str(DockerComposeManager.CONTAINER_SETUP_DIR)])