from unittest.mock import MagicMock, patch

from ade_bench.agents.agent_factory import NamedAgentFactory
from ade_bench.agents.agent_name import AgentName


def test_named_factory_creates_deep_agents_code_agent():
    agent = NamedAgentFactory(AgentName.DEEP_AGENTS_CODE).get_agent()

    assert agent.NAME is AgentName.DEEP_AGENTS_CODE


def test_perform_task_runs_dcode_headlessly_with_model_and_reasoning_effort():
    session = MagicMock()
    session.container.exec_run.return_value = MagicMock(exit_code=0, output=b"completed")
    agent = NamedAgentFactory(AgentName.DEEP_AGENTS_CODE).get_agent(
        model_name="gpt-5.4",
    )

    with (
        patch.dict(
            "os.environ",
            {
                "OPENAI_API_KEY": "test-key",
                "DEEPAGENTS_CODE_REASONING_EFFORT": "low",
            },
            clear=True,
        ),
        patch(
            "ade_bench.agents.installed_agents.abstract_installed_agent.time.monotonic",
            side_effect=[10.0, 10.5],
        ),
    ):
        result = agent.perform_task("fix user's model", session)

    command = session.send_command.call_args.args[0].command
    assert "dcode" in command
    assert "--non-interactive 'fix user'\"'\"'s model'" in command
    assert "--model gpt-5.4" in command
    assert "--model-params" in command
    assert '"effort": "low"' in command
    assert "--shell-allow-list all" in command
    assert "--no-mcp" in command
    assert result.model_name == "gpt-5.4"
    assert result.runtime_ms == 500


def test_perform_task_captures_dcode_usage_stats():
    session = MagicMock()
    session.container.exec_run.return_value = MagicMock(
        exit_code=0,
        output=b"""Task completed

Usage Stats
Provider  Model        Reqs  InputTok  OutputTok
openai    gpt-5.6-sol     9    158.3K        903

Agent active  18.7s
""",
    )
    agent = NamedAgentFactory(AgentName.DEEP_AGENTS_CODE).get_agent(
        model_name="gpt-5.6-sol",
    )

    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=True):
        result = agent.perform_task("fix the model", session)

    assert result.input_tokens == 158_300
    assert result.output_tokens == 903
    assert result.num_turns == 9
    assert result.model_name == "gpt-5.6-sol"
