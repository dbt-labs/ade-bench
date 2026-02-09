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
        """Single MCP server writes env file and runs mcp add."""
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

        # Should be called twice: once to write env file, once for mcp add
        assert session.container.exec_run.call_count == 2

        # First call: write env file
        env_write_call = session.container.exec_run.call_args_list[0]
        env_cmd = env_write_call[0][0]
        assert env_cmd[0] == "sh"
        assert env_cmd[1] == "-c"
        assert "/tmp/myserver.env" in env_cmd[2]
        assert "FOO=bar" in env_cmd[2]
        assert "BAZ=qux" in env_cmd[2]

        # Second call: mcp add
        mcp_add_call = session.container.exec_run.call_args_list[1]
        mcp_cmd = mcp_add_call[0][0]
        assert "mcp add myserver" in mcp_cmd[2]
        assert "--env-file /tmp/myserver.env" in mcp_cmd[2]
        assert "some-mcp@latest" in mcp_cmd[2]

    def test_server_without_env(self):
        """MCP server with no env vars skips env file writing."""
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

        # Only 1 call (no env file to write, but dbt detection adds nothing)
        assert session.container.exec_run.call_count == 1

        mcp_cmd = session.container.exec_run.call_args[0][0]
        assert "mcp add simple" in mcp_cmd[2]
        assert "--env-file" not in mcp_cmd[2]


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

        # Mock exec_run: first for which dbt, second for env file, third for mcp add
        which_dbt_result = MagicMock(exit_code=0, output=b"/usr/local/bin/dbt")
        default_result = MagicMock(exit_code=0, output=b"Success")
        session = _make_session(exec_results=[
            which_dbt_result,  # _get_dbt_dynamic_env: which dbt
            default_result,    # write env file
            default_result,    # mcp add
        ])

        agent._configure_mcp_servers(session, "test_task")

        # Verify which dbt was called
        first_call = session.container.exec_run.call_args_list[0]
        assert first_call[0][0] == ["sh", "-c", "which dbt"]

        # Verify env file includes dynamic vars
        env_write_call = session.container.exec_run.call_args_list[1]
        env_content = env_write_call[0][0][2]
        assert "DISABLE_SQL=true" in env_content  # static
        assert "DBT_PROJECT_DIR=" in env_content  # dynamic
        assert "DBT_PATH=/usr/local/bin/dbt" in env_content  # dynamic
        assert "DISABLE_DBT_CLI=false" in env_content  # dynamic

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
            default_result,    # env file
            default_result,    # mcp add
        ])

        agent._configure_mcp_servers(session, "test_task")

        # Dynamic dbt env vars should be present since dbt-mcp is in args
        env_write_call = session.container.exec_run.call_args_list[1]
        env_content = env_write_call[0][0][2]
        assert "DBT_PATH=/usr/bin/dbt" in env_content

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
            default_result,
        ])

        agent._configure_mcp_servers(session, "test_task")

        env_write_call = session.container.exec_run.call_args_list[1]
        env_content = env_write_call[0][0][2]
        # Static value should win over dynamic "false"
        assert "DISABLE_DBT_CLI=true" in env_content


class TestConfigureMcpServersFailure:
    def test_env_file_write_failure_logs_warning(self):
        """Non-zero exit on env file write logs warning but continues."""
        mcp_servers = {
            "myserver": McpServerConfig(
                command="uvx",
                args=["mcp@latest"],
                env={"KEY": "val"},
            )
        }
        agent = ConcreteInstalledAgent(mcp_servers=mcp_servers)

        env_fail = MagicMock(exit_code=1, output=b"Permission denied")
        mcp_success = MagicMock(exit_code=0, output=b"OK")
        session = _make_session(exec_results=[env_fail, mcp_success])

        # Should not raise
        agent._configure_mcp_servers(session, "test_task")

        # mcp add still called despite env file failure
        assert session.container.exec_run.call_count == 2

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
