import pytest
from unittest.mock import MagicMock, call
from ade_bench.plugins.skills_handler import SkillsHandler
from ade_bench.harness_models import PluginSet, SkillOrigin


def test_skills_handler_install_no_skills():
    """No-op when plugin set has no skills."""
    plugin_set = PluginSet(name="test", skills=[], allowed_tools=["Bash"])
    terminal = MagicMock()

    handler = SkillsHandler()
    handler.install(plugin_set, terminal)

    terminal.container.exec_run.assert_not_called()


def test_skills_handler_install_all_skills():
    """Installs all skills from a repo when skill_names is empty."""
    plugin_set = PluginSet(
        name="test",
        skills=[SkillOrigin(location="dbt-labs/dbt-agent-skills")],
        allowed_tools=["Bash"]
    )
    terminal = MagicMock()
    terminal.container.exec_run.return_value = MagicMock(exit_code=0, output=b"Success")

    handler = SkillsHandler()
    handler.install(plugin_set, terminal)

    terminal.container.exec_run.assert_called_once()
    call_args = terminal.container.exec_run.call_args
    cmd = call_args[0][0]
    assert "npx" in cmd[2]
    assert "skills add" in cmd[2]
    assert "dbt-labs/dbt-agent-skills" in cmd[2]
    assert "--all" in cmd[2]


def test_skills_handler_install_specific_skills():
    """Installs only specified skills when skill_names is provided."""
    plugin_set = PluginSet(
        name="test",
        skills=[SkillOrigin(
            location="dbt-labs/dbt-agent-skills",
            skill_names=["using-dbt-for-analytics-engineering", "fetching-dbt-docs"]
        )],
        allowed_tools=["Bash"]
    )
    terminal = MagicMock()
    terminal.container.exec_run.return_value = MagicMock(exit_code=0, output=b"Success")

    handler = SkillsHandler()
    handler.install(plugin_set, terminal)

    terminal.container.exec_run.assert_called_once()
    call_args = terminal.container.exec_run.call_args
    cmd = call_args[0][0]
    assert "npx" in cmd[2]
    assert "skills add" in cmd[2]
    assert "dbt-labs/dbt-agent-skills" in cmd[2]
    # Verify --skill flag syntax is used for each skill
    assert "--skill using-dbt-for-analytics-engineering" in cmd[2]
    assert "--skill fetching-dbt-docs" in cmd[2]
    assert "--all" not in cmd[2]


def test_skills_handler_install_multiple_origins():
    """Installs skills from multiple origins."""
    plugin_set = PluginSet(
        name="test",
        skills=[
            SkillOrigin(location="repo/a"),
            SkillOrigin(location="repo/b"),
        ],
        allowed_tools=["Bash"]
    )
    terminal = MagicMock()
    terminal.container.exec_run.return_value = MagicMock(exit_code=0, output=b"Success")

    handler = SkillsHandler()
    handler.install(plugin_set, terminal)

    assert terminal.container.exec_run.call_count == 2


def test_skills_handler_install_failure_logs_warning():
    """Logs warning but doesn't raise on install failure."""
    plugin_set = PluginSet(
        name="test",
        skills=[SkillOrigin(location="repo/failing")],
        allowed_tools=["Bash"]
    )
    terminal = MagicMock()
    terminal.container.exec_run.return_value = MagicMock(
        exit_code=1,
        output=b"npm ERR! not found"
    )

    handler = SkillsHandler()
    # Should not raise, just log warning
    handler.install(plugin_set, terminal)
