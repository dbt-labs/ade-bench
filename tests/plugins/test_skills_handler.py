import pytest
from unittest.mock import MagicMock, call
from ade_bench.plugins.skills_handler import SkillsHandler
from ade_bench.models.skill_set import SkillSet


def test_skills_handler_install_no_skills():
    """No-op when skill set has no skills."""
    skill_set = SkillSet(name="test", skills=[], allowed_tools=["Bash"])
    terminal = MagicMock()

    handler = SkillsHandler()
    handler.install(skill_set, terminal)

    terminal.container.exec_run.assert_not_called()


def test_skills_handler_install_single_skill():
    """Installs a single skill repo."""
    skill_set = SkillSet(
        name="test",
        skills=["dbt-labs/dbt-agent-skills"],
        allowed_tools=["Bash"]
    )
    terminal = MagicMock()
    terminal.container.exec_run.return_value = MagicMock(exit_code=0, output=b"Success")

    handler = SkillsHandler()
    handler.install(skill_set, terminal)

    terminal.container.exec_run.assert_called_once()
    call_args = terminal.container.exec_run.call_args
    cmd = call_args[0][0]
    assert "npx" in cmd[2]
    assert "skills add" in cmd[2]
    assert "dbt-labs/dbt-agent-skills" in cmd[2]


def test_skills_handler_install_multiple_skills():
    """Installs multiple skill repos."""
    skill_set = SkillSet(
        name="test",
        skills=["repo/a", "repo/b"],
        allowed_tools=["Bash"]
    )
    terminal = MagicMock()
    terminal.container.exec_run.return_value = MagicMock(exit_code=0, output=b"Success")

    handler = SkillsHandler()
    handler.install(skill_set, terminal)

    assert terminal.container.exec_run.call_count == 2


def test_skills_handler_install_failure_logs_warning():
    """Logs warning but doesn't raise on install failure."""
    skill_set = SkillSet(
        name="test",
        skills=["repo/failing"],
        allowed_tools=["Bash"]
    )
    terminal = MagicMock()
    terminal.container.exec_run.return_value = MagicMock(
        exit_code=1,
        output=b"npm ERR! not found"
    )

    handler = SkillsHandler()
    # Should not raise, just log warning
    handler.install(skill_set, terminal)
