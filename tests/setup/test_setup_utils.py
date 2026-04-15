from unittest.mock import MagicMock
from ade_bench.setup.setup_utils import run_script_checked


def test_run_script_checked_returns_zero_on_success():
    session = MagicMock()
    container = MagicMock()
    container.exec_run.return_value = MagicMock(output=b"0\n")

    result = run_script_checked(session, container, "bash /app/test.sh")

    session.send_keys.assert_called_once_with(
        ["bash /app/test.sh; echo $? > /tmp/.ade_exit_code", "Enter"],
        block=True,
        max_timeout_sec=180.0,
    )
    container.exec_run.assert_called_once_with(["cat", "/tmp/.ade_exit_code"])
    assert result == 0


def test_run_script_checked_returns_nonzero_on_failure():
    session = MagicMock()
    container = MagicMock()
    container.exec_run.return_value = MagicMock(output=b"1\n")

    result = run_script_checked(session, container, "bash /app/test.sh")

    assert result == 1


def test_run_script_checked_passes_max_timeout():
    session = MagicMock()
    container = MagicMock()
    container.exec_run.return_value = MagicMock(output=b"0\n")

    run_script_checked(session, container, "bash /app/test.sh", max_timeout_sec=float("inf"))

    session.send_keys.assert_called_once_with(
        ["bash /app/test.sh; echo $? > /tmp/.ade_exit_code", "Enter"],
        block=True,
        max_timeout_sec=float("inf"),
    )


def test_run_script_checked_returns_one_when_exit_code_file_absent():
    """If the shell crashes before writing the exit code file, treat as failure."""
    session = MagicMock()
    container = MagicMock()
    container.exec_run.return_value = MagicMock(output=b"")

    result = run_script_checked(session, container, "bash /app/test.sh")

    assert result == 1
