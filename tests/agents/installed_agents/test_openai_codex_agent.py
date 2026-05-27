from unittest.mock import patch

from ade_bench.agents.installed_agents.openai_codex.openai_codex_agent import (
    OpenAICodexAgent,
)


class TestReasoningEffortEnvVar:
    def test_no_env_var_omits_flag(self):
        """When OPENAI_CODEX_REASONING_EFFORT is unset, no -c flag is emitted."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "key"}, clear=False):
            agent = OpenAICodexAgent()
            commands = agent._run_agent_commands("do the thing")
        assert "model_reasoning_effort" not in commands[0].command

    def test_env_var_emits_config_flag(self):
        """When set, the value is passed via -c model_reasoning_effort=<value>."""
        env = {"OPENAI_API_KEY": "key", "OPENAI_CODEX_REASONING_EFFORT": "low"}
        with patch.dict("os.environ", env, clear=False):
            agent = OpenAICodexAgent()
            commands = agent._run_agent_commands("do the thing")
        assert "-c model_reasoning_effort=low" in commands[0].command

    def test_env_var_value_is_shell_quoted(self):
        """Value goes through shlex.quote so injection attempts are inert."""
        env = {
            "OPENAI_API_KEY": "key",
            "OPENAI_CODEX_REASONING_EFFORT": "low; rm -rf /",
        }
        with patch.dict("os.environ", env, clear=False):
            agent = OpenAICodexAgent()
            commands = agent._run_agent_commands("do the thing")
        # The whole key=value pair is one shell-quoted token, so `rm -rf /` is
        # part of the quoted argument — never a second command.
        assert "rm -rf /" not in commands[0].command.replace(
            "'model_reasoning_effort=low; rm -rf /'", ""
        )
