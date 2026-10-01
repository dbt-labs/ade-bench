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


class TestAuthEnv:
    def test_api_key_default(self):
        env = {"ANTHROPIC_API_KEY": "key"}
        with patch.dict("os.environ", env, clear=True):
            agent = ClaudeCodeAgent()
            assert agent._env == {"ANTHROPIC_API_KEY": "key"}

    def test_oauth_token_preferred(self):
        """A subscription OAuth token takes precedence over an API key."""
        env = {"ANTHROPIC_API_KEY": "key", "CLAUDE_CODE_OAUTH_TOKEN": "oat"}
        with patch.dict("os.environ", env, clear=True):
            agent = ClaudeCodeAgent()
            assert agent._env == {"CLAUDE_CODE_OAUTH_TOKEN": "oat"}

    def test_whitespace_oauth_token_treated_as_unset(self):
        """A whitespace-only token must not shadow a valid API key."""
        env = {"ANTHROPIC_API_KEY": "key", "CLAUDE_CODE_OAUTH_TOKEN": "  "}
        with patch.dict("os.environ", env, clear=True):
            agent = ClaudeCodeAgent()
            assert agent._env == {"ANTHROPIC_API_KEY": "key"}

    def test_oauth_token_without_api_key(self):
        """OAuth-only environments must not require ANTHROPIC_API_KEY."""
        env = {"CLAUDE_CODE_OAUTH_TOKEN": "oat"}
        with patch.dict("os.environ", env, clear=True):
            agent = ClaudeCodeAgent()
            assert agent._env == {"CLAUDE_CODE_OAUTH_TOKEN": "oat"}
