import pytest
from unittest.mock import MagicMock, call
from ade_bench.plugins.mcp_handler import McpHandler
from ade_bench.models.plugin_set import PluginSet, McpServerConfig


def test_mcp_handler_configure_no_servers():
    """No-op when plugin set has no MCP servers."""
    plugin_set = PluginSet(name="test", mcp_servers={}, allowed_tools=["Bash"])
    terminal = MagicMock()

    handler = McpHandler()
    handler.configure(plugin_set, "claude", terminal)

    terminal.container.exec_run.assert_not_called()


def test_mcp_handler_configure_single_server():
    """Configures a single MCP server."""
    plugin_set = PluginSet(
        name="test",
        mcp_servers={
            "dbt": McpServerConfig(command="uvx", args=["dbt-mcp@latest"])
        },
        allowed_tools=["Bash"]
    )
    terminal = MagicMock()
    terminal.container.exec_run.return_value = MagicMock(exit_code=0, output=b"Success")

    handler = McpHandler()
    handler.configure(plugin_set, "claude", terminal)

    # Should have at least one call for mcp add
    assert terminal.container.exec_run.call_count >= 1
    calls = terminal.container.exec_run.call_args_list
    # Find the mcp add call
    mcp_add_call = [c for c in calls if "mcp add" in str(c)]
    assert len(mcp_add_call) >= 1


def test_mcp_handler_configure_with_env():
    """Writes env file when env vars are specified."""
    plugin_set = PluginSet(
        name="test",
        mcp_servers={
            "dbt": McpServerConfig(
                command="uvx",
                args=["dbt-mcp@latest"],
                env={"DISABLE_SQL": "true", "DISABLE_DISCOVERY": "true"}
            )
        },
        allowed_tools=["Bash"]
    )
    terminal = MagicMock()
    terminal.container.exec_run.return_value = MagicMock(exit_code=0, output=b"Success")

    handler = McpHandler()
    handler.configure(plugin_set, "claude", terminal)

    # Check that env file was written
    calls = terminal.container.exec_run.call_args_list
    env_write_calls = [c for c in calls if "DISABLE_SQL" in str(c)]
    assert len(env_write_calls) >= 1


def test_mcp_handler_configure_different_agents():
    """Uses correct agent CLI command."""
    plugin_set = PluginSet(
        name="test",
        mcp_servers={
            "dbt": McpServerConfig(command="uvx", args=["dbt-mcp"])
        },
        allowed_tools=["Bash"]
    )
    terminal = MagicMock()
    terminal.container.exec_run.return_value = MagicMock(exit_code=0, output=b"Success")

    handler = McpHandler()

    # Test claude
    handler.configure(plugin_set, "claude", terminal)
    calls = terminal.container.exec_run.call_args_list
    claude_calls = [c for c in calls if "claude mcp add" in str(c)]
    assert len(claude_calls) >= 1

    terminal.reset_mock()

    # Test gemini
    handler.configure(plugin_set, "gemini", terminal)
    calls = terminal.container.exec_run.call_args_list
    gemini_calls = [c for c in calls if "gemini mcp add" in str(c)]
    assert len(gemini_calls) >= 1
