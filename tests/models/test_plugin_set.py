import pytest
from ade_bench.models.plugin_set import PluginSet, McpServerConfig, PluginSetsConfig


def test_mcp_server_config_minimal():
    config = McpServerConfig(command="uvx", args=["dbt-mcp@latest"])
    assert config.command == "uvx"
    assert config.args == ["dbt-mcp@latest"]
    assert config.env == {}


def test_mcp_server_config_with_env():
    config = McpServerConfig(
        command="uvx",
        args=["dbt-mcp@latest"],
        env={"DISABLE_SQL": "true"}
    )
    assert config.env == {"DISABLE_SQL": "true"}


def test_plugin_set_minimal():
    plugin_set = PluginSet(name="test", allowed_tools=["Bash"])
    assert plugin_set.name == "test"
    assert plugin_set.description == ""
    assert plugin_set.default is False
    assert plugin_set.agents is None
    assert plugin_set.skills == []
    assert plugin_set.mcp_servers == {}
    assert plugin_set.allowed_tools == ["Bash"]


def test_plugin_set_full():
    plugin_set = PluginSet(
        name="dbt-full",
        description="Full dbt setup",
        default=True,
        agents=["claude"],
        skills=["dbt-labs/dbt-agent-skills"],
        mcp_servers={
            "dbt": McpServerConfig(command="uvx", args=["dbt-mcp@latest"])
        },
        allowed_tools=["Bash", "Skill", "mcp__dbt__*"]
    )
    assert plugin_set.default is True
    assert plugin_set.agents == ["claude"]
    assert len(plugin_set.mcp_servers) == 1


def test_plugin_set_is_compatible_with_agent_all():
    """When agents is None, compatible with all agents."""
    plugin_set = PluginSet(name="test", allowed_tools=["Bash"])
    assert plugin_set.is_compatible_with_agent("claude") is True
    assert plugin_set.is_compatible_with_agent("gemini") is True


def test_plugin_set_is_compatible_with_agent_restricted():
    """When agents is set, only compatible with listed agents."""
    plugin_set = PluginSet(name="test", agents=["claude"], allowed_tools=["Bash"])
    assert plugin_set.is_compatible_with_agent("claude") is True
    assert plugin_set.is_compatible_with_agent("gemini") is False


def test_plugin_sets_config_from_yaml():
    yaml_content = """
sets:
  - name: no-plugins
    default: true
    skills: []
    allowed_tools: [Bash, Read]
  - name: dbt-skills
    agents: [claude]
    skills:
      - dbt-labs/dbt-agent-skills
    allowed_tools: [Bash, Skill]
"""
    import yaml
    data = yaml.safe_load(yaml_content)
    config = PluginSetsConfig(**data)
    assert len(config.sets) == 2
    assert config.sets[0].name == "no-plugins"
    assert config.sets[0].default is True


def test_plugin_sets_config_get_defaults():
    config = PluginSetsConfig(sets=[
        PluginSet(name="a", default=True, allowed_tools=["Bash"]),
        PluginSet(name="b", default=False, allowed_tools=["Bash"]),
        PluginSet(name="c", default=True, allowed_tools=["Bash"]),
    ])
    defaults = config.get_defaults()
    assert len(defaults) == 2
    assert defaults[0].name == "a"
    assert defaults[1].name == "c"


def test_plugin_sets_config_get_by_name():
    config = PluginSetsConfig(sets=[
        PluginSet(name="a", allowed_tools=["Bash"]),
        PluginSet(name="b", allowed_tools=["Bash"]),
    ])
    assert config.get_by_name("a").name == "a"
    assert config.get_by_name("b").name == "b"
    assert config.get_by_name("nonexistent") is None


def test_plugin_sets_config_get_by_names():
    config = PluginSetsConfig(sets=[
        PluginSet(name="a", allowed_tools=["Bash"]),
        PluginSet(name="b", allowed_tools=["Bash"]),
        PluginSet(name="c", allowed_tools=["Bash"]),
    ])
    result = config.get_by_names(["a", "c"])
    assert len(result) == 2
    assert result[0].name == "a"
    assert result[1].name == "c"


def test_plugin_sets_config_get_by_names_unknown_raises():
    config = PluginSetsConfig(sets=[
        PluginSet(name="a", allowed_tools=["Bash"]),
    ])
    with pytest.raises(ValueError, match="Unknown plugin set"):
        config.get_by_names(["a", "nonexistent"])
