"""
DuckDB setup functions.
"""

from typing import Dict, Any, Tuple
from ..terminal.docker_compose_manager import DockerComposeManager


def setup_duckdb(terminal, session, variant: Dict[str, Any], trial_handler) -> Tuple[bool, str]:
    """Setup DuckDB by copying the database file.

    Returns:
        Tuple of (success, error_message). error_message is empty string on success.
    """
    db_name = variant.get('db_name')
    db_dir = variant.get('db_dir')

    if not db_name:
        return True, ""

    db_file_path = trial_handler.get_duckdb_file_path(db_name, db_dir)

    if not db_file_path.exists():
        if db_dir:
            return False, f"DuckDB database '{db_name}' not found in directory: {db_file_path}"
        else:
            return False, f"DuckDB database '{db_name}' not found at {db_file_path}"

    terminal.copy_to_container(
        paths=db_file_path,
        container_dir=str(DockerComposeManager.CONTAINER_APP_DIR),
        container_filename=f"{db_name}.duckdb"
    )
    return True, ""
