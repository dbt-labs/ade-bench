import pytest
from unittest.mock import MagicMock, call, patch
from pathlib import Path

from ade_bench.agents.agent_name import AgentName
from ade_bench.agents.installed_agents.abstract_installed_agent import AbstractInstalledAgent
from ade_bench.harness_models import McpServerConfig, TerminalCommand


class ConcreteInstalledAgent(AbstractInstalledAgent):
    """Concrete subclass for testing AbstractInstalledAgent."""
    NAME = AgentName.CLAUDE_CODE

    @property
    def _env(self) -> dict[str, str]:
        return {"TEST_KEY": "test_value"}

    @property
    def _install_agent_script(self) -> Path:
        return Path("/fake/install.sh")

    def _run_agent_commands(self, task_prompt: str) -> list[TerminalCommand]:
        return []


def _make_session(exec_results=None):
    """Create a mock TmuxSession with configurable exec_run results."""
    session = MagicMock()
    if exec_results is None:
        session.container.exec_run.return_value = MagicMock(
            exit_code=0, output=b"Success"
        )
    else:
        session.container.exec_run.side_effect = exec_results
    return session


class TestConfigureMcpServersNoop:
    def test_no_mcp_servers(self):
        """No calls when mcp_servers is empty."""
        agent = ConcreteInstalledAgent(mcp_servers={})
        session = _make_session()
        agent._configure_mcp_servers(session, "test_task")
        session.container.exec_run.assert_not_called()


class TestConfigureMcpServersBasic:
    def test_single_server_with_env(self):
        """Single MCP server passes env vars via -e flags."""
        mcp_servers = {
            "myserver": McpServerConfig(
                command="uvx",
                args=["some-mcp@latest"],
                env={"FOO": "bar", "BAZ": "qux"},
            )
        }
        agent = ConcreteInstalledAgent(mcp_servers=mcp_servers)
        session = _make_session()

        agent._configure_mcp_servers(session, "test_task")

        # Single call: mcp add with -e flags
        assert session.container.exec_run.call_count == 1

        mcp_cmd = session.container.exec_run.call_args[0][0]
        assert "mcp add" in mcp_cmd[2]
        assert "-e FOO=bar" in mcp_cmd[2]
        assert "-e BAZ=qux" in mcp_cmd[2]
        assert "myserver" in mcp_cmd[2]
        assert "some-mcp@latest" in mcp_cmd[2]

    def test_server_without_env(self):
        """MCP server with no env vars has no -e flags."""
        mcp_servers = {
            "simple": McpServerConfig(
                command="npx",
                args=["simple-mcp"],
                env={},
            )
        }
        agent = ConcreteInstalledAgent(mcp_servers=mcp_servers)
        session = _make_session()

        agent._configure_mcp_servers(session, "test_task")

        assert session.container.exec_run.call_count == 1

        mcp_cmd = session.container.exec_run.call_args[0][0]
        assert "mcp add simple" in mcp_cmd[2]
        assert "-e " not in mcp_cmd[2]


class TestConfigureMcpServersDbtDetection:
    def test_dbt_server_by_name(self):
        """dbt MCP server detected by server name 'dbt'."""
        mcp_servers = {
            "dbt": McpServerConfig(
                command="uvx",
                args=["dbt-mcp@latest"],
                env={"DISABLE_SQL": "true"},
            )
        }
        agent = ConcreteInstalledAgent(mcp_servers=mcp_servers)

        # Mock exec_run: first for which dbt, second for mcp add
        which_dbt_result = MagicMock(exit_code=0, output=b"/usr/local/bin/dbt")
        default_result = MagicMock(exit_code=0, output=b"Success")
        session = _make_session(exec_results=[
            which_dbt_result,  # _get_dbt_dynamic_env: which dbt
            default_result,    # mcp add
        ])

        agent._configure_mcp_servers(session, "test_task")

        # Verify which dbt was called
        first_call = session.container.exec_run.call_args_list[0]
        assert first_call[0][0] == ["sh", "-c", "which dbt"]

        # Verify mcp add includes all env vars as -e flags
        mcp_add_call = session.container.exec_run.call_args_list[1]
        mcp_cmd = mcp_add_call[0][0][2]
        assert "-e DISABLE_SQL=true" in mcp_cmd  # static
        assert "-e DBT_PROJECT_DIR=" in mcp_cmd  # dynamic
        assert "-e DBT_PATH=/usr/local/bin/dbt" in mcp_cmd  # dynamic
        assert "-e DISABLE_DBT_CLI=false" in mcp_cmd  # dynamic

    def test_dbt_server_by_args(self):
        """dbt MCP server detected by 'dbt-mcp' in args."""
        mcp_servers = {
            "data-tools": McpServerConfig(
                command="uvx",
                args=["dbt-mcp@latest"],
                env={},
            )
        }
        agent = ConcreteInstalledAgent(mcp_servers=mcp_servers)

        which_dbt_result = MagicMock(exit_code=0, output=b"/usr/bin/dbt")
        default_result = MagicMock(exit_code=0, output=b"Success")
        session = _make_session(exec_results=[
            which_dbt_result,  # which dbt
            default_result,    # mcp add
        ])

        agent._configure_mcp_servers(session, "test_task")

        # Dynamic dbt env vars should be present as -e flags
        mcp_add_call = session.container.exec_run.call_args_list[1]
        mcp_cmd = mcp_add_call[0][0][2]
        assert "-e DBT_PATH=/usr/bin/dbt" in mcp_cmd

    def test_static_env_takes_precedence(self):
        """Static env vars from config are not overridden by dynamic vars."""
        mcp_servers = {
            "dbt": McpServerConfig(
                command="uvx",
                args=["dbt-mcp@latest"],
                env={"DISABLE_DBT_CLI": "true"},  # static override
            )
        }
        agent = ConcreteInstalledAgent(mcp_servers=mcp_servers)

        which_dbt_result = MagicMock(exit_code=0, output=b"/usr/bin/dbt")
        default_result = MagicMock(exit_code=0, output=b"Success")
        session = _make_session(exec_results=[
            which_dbt_result,
            default_result,
        ])

        agent._configure_mcp_servers(session, "test_task")

        mcp_add_call = session.container.exec_run.call_args_list[1]
        mcp_cmd = mcp_add_call[0][0][2]
        # Static value should win over dynamic "false"
        assert "-e DISABLE_DBT_CLI=true" in mcp_cmd


class TestConfigureMcpServersFailure:
    def test_mcp_add_failure_logs_warning(self):
        """Non-zero exit on mcp add logs warning but doesn't raise."""
        mcp_servers = {
            "myserver": McpServerConfig(
                command="uvx",
                args=["mcp@latest"],
                env={},
            )
        }
        agent = ConcreteInstalledAgent(mcp_servers=mcp_servers)

        mcp_fail = MagicMock(exit_code=1, output=b"Command not found")
        session = _make_session(exec_results=[mcp_fail])

        # Should not raise
        agent._configure_mcp_servers(session, "test_task")


class TestCopyLogFileFromContainer:
    def test_copies_log_file_successfully(self, tmp_path):
        """Reads /tmp/agent_output.log from container and writes to logging_dir."""
        agent = ConcreteInstalledAgent()
        container = MagicMock()
        container.exec_run.return_value = MagicMock(
            exit_code=0, output=b"some agent output\nwith multiple lines"
        )

        result = agent._copy_log_file_from_container(container, tmp_path)

        container.exec_run.assert_called_once_with(["cat", "/tmp/agent_output.log"])
        assert result == "some agent output\nwith multiple lines"
        assert (tmp_path / "agent_output.log").read_text() == "some agent output\nwith multiple lines"

    def test_returns_empty_string_on_nonzero_exit(self, tmp_path):
        """Returns empty string when cat command fails (file not found)."""
        agent = ConcreteInstalledAgent()
        container = MagicMock()
        container.exec_run.return_value = MagicMock(
            exit_code=1, output=b"No such file or directory"
        )

        result = agent._copy_log_file_from_container(container, tmp_path)

        assert result == ""
        assert not (tmp_path / "agent_output.log").exists()

    def test_returns_empty_string_on_exception(self, tmp_path):
        """Returns empty string when container exec raises an exception."""
        agent = ConcreteInstalledAgent()
        container = MagicMock()
        container.exec_run.side_effect = Exception("Container is dead")

        result = agent._copy_log_file_from_container(container, tmp_path)

        assert result == ""
