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


def run_script_checked(session, container, command: str, max_timeout_sec: float = 180.0) -> int:
    """Run a shell command via tmux and return its exit code.

    Appends an exit-code capture to the command before signalling tmux done,
    then reads the captured value back via exec_run. This is necessary because
    send_keys only waits for the tmux signal and never sees the command's exit code.
    """
    checked = f"{command}; echo $? > /tmp/.ade_exit_code"
    session.send_keys([checked, "Enter"], block=True, max_timeout_sec=max_timeout_sec)
    result = container.exec_run(["cat", "/tmp/.ade_exit_code"])
    output = result.output.decode().strip()
    return int(output) if output else 1
