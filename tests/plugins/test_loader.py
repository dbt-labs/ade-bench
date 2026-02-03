import pytest
from pathlib import Path
from ade_bench.plugins.loader import SkillSetLoader
from ade_bench.models.skill_set import SkillSetsConfig


def test_loader_loads_yaml(tmp_path):
    yaml_file = tmp_path / "skill-sets.yaml"
    yaml_file.write_text("""
sets:
  - name: test
    default: true
    skills: []
    allowed_tools: [Bash]
""")
    loader = SkillSetLoader(yaml_file)
    config = loader.load()
    assert isinstance(config, SkillSetsConfig)
    assert len(config.sets) == 1
    assert config.sets[0].name == "test"


def test_loader_file_not_found():
    loader = SkillSetLoader(Path("/nonexistent/skill-sets.yaml"))
    with pytest.raises(FileNotFoundError):
        loader.load()


def test_loader_resolve_skill_sets_explicit():
    """Explicit --plugin-set names are resolved."""
    yaml_content = """
sets:
  - name: a
    default: false
    allowed_tools: [Bash]
  - name: b
    default: true
    allowed_tools: [Bash]
"""
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_content)
        f.flush()
        loader = SkillSetLoader(Path(f.name))
        result = loader.resolve_skill_sets(
            plugin_set_names=["a"],
            agent_name="claude"
        )
        assert len(result) == 1
        assert result[0].name == "a"


def test_loader_resolve_skill_sets_defaults():
    """When no --plugin-set, use defaults."""
    yaml_content = """
sets:
  - name: a
    default: false
    allowed_tools: [Bash]
  - name: b
    default: true
    allowed_tools: [Bash]
  - name: c
    default: true
    allowed_tools: [Bash]
"""
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_content)
        f.flush()
        loader = SkillSetLoader(Path(f.name))
        result = loader.resolve_skill_sets(
            plugin_set_names=None,
            agent_name="claude"
        )
        assert len(result) == 2
        assert result[0].name == "b"
        assert result[1].name == "c"


def test_loader_resolve_skill_sets_filters_incompatible():
    """Skill sets incompatible with agent are filtered out."""
    yaml_content = """
sets:
  - name: claude-only
    default: true
    agents: [claude]
    allowed_tools: [Bash]
  - name: all-agents
    default: true
    allowed_tools: [Bash]
"""
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_content)
        f.flush()
        loader = SkillSetLoader(Path(f.name))

        # Claude gets both
        result = loader.resolve_skill_sets(None, "claude")
        assert len(result) == 2

        # Gemini only gets all-agents
        result = loader.resolve_skill_sets(None, "gemini")
        assert len(result) == 1
        assert result[0].name == "all-agents"


def test_loader_resolve_skill_sets_error_on_incompatible_explicit():
    """Error when explicitly requested skill set is incompatible."""
    yaml_content = """
sets:
  - name: claude-only
    agents: [claude]
    allowed_tools: [Bash]
"""
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_content)
        f.flush()
        loader = SkillSetLoader(Path(f.name))

        with pytest.raises(ValueError, match="not compatible with agent 'gemini'"):
            loader.resolve_skill_sets(["claude-only"], "gemini")


def test_loader_resolve_skill_sets_error_when_none_compatible():
    """Error when no skill sets are compatible with agent."""
    yaml_content = """
sets:
  - name: claude-only
    default: true
    agents: [claude]
    allowed_tools: [Bash]
"""
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_content)
        f.flush()
        loader = SkillSetLoader(Path(f.name))

        with pytest.raises(ValueError, match="No compatible skill sets"):
            loader.resolve_skill_sets(None, "gemini")
