"""
Migration setup functions.
"""

from typing import Dict, Any
from ..terminal.docker_compose_manager import DockerComposeManager
from .setup_utils import run_script_checked


def setup_migration(terminal, session, variant: Dict[str, Any], trial_handler) -> None:
    """Setup migration by copying migration files."""
    migration_directory = variant.get("migration_directory")

    if not migration_directory:
        return

    migration_dir_path = trial_handler.get_migration_path(migration_directory)
    migration_script_path = trial_handler.get_migration_script_path(migration_directory)

    if session is None:
        raise RuntimeError(
            f"Cannot run migration '{migration_directory}': no tmux session available"
        )

    if migration_dir_path.exists():
        terminal.copy_to_container(
            paths=migration_script_path,
            container_dir=str(DockerComposeManager.CONTAINER_APP_DIR),
            container_filename="migration.sh",
        )

        terminal.copy_to_container(
            paths=migration_dir_path,
            container_dir=str(DockerComposeManager.CONTAINER_MIGRATION_DIR),
        )

        # Run migration script (if it was copied in step 3)
        migration_command = f"bash {DockerComposeManager.CONTAINER_APP_DIR}/migration.sh"
        exit_code = run_script_checked(session, session.container, migration_command)
        if exit_code != 0:
            raise RuntimeError(
                f"migration.sh failed with exit code {exit_code} for directory: {migration_directory}"
            )
        session.container.exec_run(["rm", f"{DockerComposeManager.CONTAINER_APP_DIR}/migration.sh"])
        session.container.exec_run(["rm", "-rf", str(DockerComposeManager.CONTAINER_MIGRATION_DIR)])
