"""
Utilities for setup functions.
"""

import os
import subprocess
import tempfile
from typing import Dict


def generate_task_snowflake_credentials(task_id: str) -> Dict[str, str]:
    """Generate Snowflake credentials for a specific task (the user created during setup)."""
    modified_task_id = task_id.replace(".", "_")
    temp_slug = f"temp_ade_{modified_task_id}".upper()
    username = f"{temp_slug}_USER"
    password = f"{temp_slug}_password_123"
    role_name = f"{temp_slug}_ROLE"
    database_name = f"{temp_slug}_DATABASE"

    return {
        "account": os.getenv("SNOWFLAKE_ACCOUNT"),
        "user": username,
        "password": password,
        "role": role_name,
        "database": database_name,
        "schema": "PUBLIC",
        "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE"),
    }


def update_file_in_container(container, file_path: str, update_func, *args, **kwargs):
    """Read file from container, apply update function, write back to container."""
    with tempfile.NamedTemporaryFile(mode="w+", suffix=".tmp", delete=False) as temp_file:
        temp_path = temp_file.name

        try:
            # Copy file FROM container to temp
            subprocess.run(
                ["docker", "cp", f"{container.name}:{file_path}", temp_path],
                check=True,
                capture_output=True,
            )

            # Apply update function
            update_func(temp_path, *args, **kwargs)

            # Copy file back TO container
            subprocess.run(
                ["docker", "cp", temp_path, f"{container.name}:{file_path}"],
                check=True,
                capture_output=True,
            )

        finally:
            os.unlink(temp_path)
