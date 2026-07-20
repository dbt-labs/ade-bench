from unittest.mock import patch

from ade_bench.agents.installed_agents.claude_code.claude_code_agent import (
    ClaudeCodeAgent,
)


class TestEffortEnvVar:
    def test_no_env_var_omits_flag(self):
        """When CLAUDE_CODE_EFFORT is unset, no --effort flag is emitted."""
        env = {"ANTHROPIC_API_KEY": "key"}
        with patch.dict("os.environ", env, clear=True):
            agent = ClaudeCodeAgent()
            commands = agent._run_agent_commands("do the thing")
        assert "--effort" not in commands[0].command

    def test_env_var_emits_effort_flag(self):
        """When set, the value is passed via --effort <value>."""
        env = {"ANTHROPIC_API_KEY": "key", "CLAUDE_CODE_EFFORT": "low"}
        with patch.dict("os.environ", env, clear=True):
            agent = ClaudeCodeAgent()
            commands = agent._run_agent_commands("do the thing")
        assert "--effort low" in commands[0].command

    def test_env_var_value_is_shell_quoted(self):
        """Value goes through shlex.quote so injection attempts are inert."""
        env = {
            "ANTHROPIC_API_KEY": "key",
            "CLAUDE_CODE_EFFORT": "low; rm -rf /",
        }
        with patch.dict("os.environ", env, clear=True):
            agent = ClaudeCodeAgent()
            commands = agent._run_agent_commands("do the thing")
        # The whole value is one shell-quoted token, so `rm -rf /` is part of
        # the quoted argument — never a second command.
        assert "--effort 'low; rm -rf /'" in commands[0].command
