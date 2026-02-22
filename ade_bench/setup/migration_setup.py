"""
Migration setup functions.
"""

from typing import Dict, Any
from ..terminal.docker_compose_manager import DockerComposeManager


def setup_migration(terminal, session, variant: Dict[str, Any], trial_handler) -> None:
    """Setup migration by copying migration files."""
    migration_directory = variant.get("migration_directory")

    if not migration_directory:
        return

    migration_dir_path = trial_handler.get_migration_path(migration_directory)
    migration_script_path = trial_handler.get_migration_script_path(migration_directory)

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
        session.send_keys(
            [f"bash {DockerComposeManager.CONTAINER_APP_DIR}/migration.sh", "Enter"], block=True
        )
        session.container.exec_run(["rm", f"{DockerComposeManager.CONTAINER_APP_DIR}/migration.sh"])
        session.container.exec_run(["rm", "-rf", str(DockerComposeManager.CONTAINER_MIGRATION_DIR)])
