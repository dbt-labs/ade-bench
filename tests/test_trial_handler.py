import subprocess
from ade_bench.handlers.trial_handler import TrialHandler


def test_get_repo_root_from_main_directory(tmp_path):
    """Test finding repo root from main directory.

    This test verifies that _get_repo_root finds the ade-bench repository root,
    not the task's temporary directory. The method looks at where the code is
    running from (trial_handler.py location), not where the task is.
    """
    # Setup: Create a git repo for the task (but handler will find ade-bench repo)
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)

    # Create a trial handler (we'll need a minimal task.yaml)
    task_dir = repo / "tasks" / "test_task"
    task_dir.mkdir(parents=True)
    (task_dir / "task.yaml").write_text("""
prompts:
  - key: base
    prompt: "test"
author_name: test
author_email: test@test.com
difficulty: easy
""")

    handler = TrialHandler(
        trial_name="test",
        input_path=task_dir,
        task_key="base"
    )

    root = handler._get_repo_root()
    # Should find the ade-bench repo root (where trial_handler.py lives)
    # Not the temporary test repo
    assert root.exists()
    assert (root / ".git").exists()
    # Verify we're in a git repository (ade-bench)
    assert root.name in ["ade-bench", "agent-install-phase"]


def test_get_repo_root_from_worktree(tmp_path):
    """Test finding repo root from worktree.

    This verifies that when code runs from a worktree, _get_repo_root correctly
    finds the main repository root, not the worktree location. This test
    checks that the method works in the actual ade-bench worktree we're running from.
    """
    # Setup: Create a git repo with worktree (but handler will find ade-bench repo)
    main_repo = tmp_path / "main"
    main_repo.mkdir()
    subprocess.run(["git", "init"], cwd=main_repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=main_repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=main_repo, check=True)

    # Create initial commit
    (main_repo / "test.txt").write_text("test")
    subprocess.run(["git", "add", "."], cwd=main_repo, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=main_repo, check=True)

    # Create worktree
    worktree = tmp_path / "worktree"
    subprocess.run(
        ["git", "worktree", "add", str(worktree), "-b", "feature"],
        cwd=main_repo,
        check=True,
        capture_output=True
    )

    # Create task in worktree
    task_dir = worktree / "tasks" / "test_task"
    task_dir.mkdir(parents=True)
    (task_dir / "task.yaml").write_text("""
prompts:
  - key: base
    prompt: "test"
author_name: test
author_email: test@test.com
difficulty: easy
""")

    handler = TrialHandler(
        trial_name="test",
        input_path=task_dir,
        task_key="base"
    )

    root = handler._get_repo_root()
    # Should find the ade-bench repo root (where trial_handler.py lives)
    # The code is running from a worktree, so this verifies worktree handling
    assert root.exists()
    assert (root / ".git").exists()
    # If we're running from agent-install-phase worktree, it should find main ade-bench
    # The root should NOT contain ".worktrees" in its path
    assert ".worktrees" not in str(root)


def test_shared_databases_root_path_in_main_repo(tmp_path):
    """Test that shared_databases_root_path points to ade-bench repo databases.

    This test verifies that shared_databases_root_path returns the ade-bench
    repository's shared/databases directory, not the task's temporary directory.
    The property looks at where the code is running from (trial_handler.py location),
    not where the task is located.
    """
    # Setup: Create a git repo for the task (but handler will find ade-bench repo)
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)

    # Create a task
    task_dir = repo / "tasks" / "test_task"
    task_dir.mkdir(parents=True)
    (task_dir / "task.yaml").write_text("""
prompts:
  - key: base
    prompt: "test"
author_name: test
author_email: test@test.com
difficulty: easy
""")

    handler = TrialHandler(
        trial_name="test",
        input_path=task_dir,
        task_key="base"
    )

    # Should point to ade-bench's shared/databases, not the temp repo
    db_path = handler.shared_databases_root_path
    assert db_path.exists()
    # Verify it's pointing to ade-bench or agent-install-phase (worktree)
    assert "ade-bench" in str(db_path) or "agent-install-phase" in str(db_path)
    assert db_path.name == "databases"
    assert db_path.parent.name == "shared"


def test_shared_databases_root_path_in_worktree(tmp_path):
    """Test that shared_databases_root_path points to main ade-bench repo.

    This verifies that when code runs from a worktree (agent-install-phase),
    shared_databases_root_path correctly finds the main ade-bench repository's
    databases, not the worktree location. This test creates a temporary task but
    verifies the handler finds the actual ade-bench repo databases.
    """
    # Setup: Create a git repo with worktree for the task
    # (but handler will find ade-bench repo, not this temp repo)
    main_repo = tmp_path / "main"
    main_repo.mkdir()
    subprocess.run(["git", "init"], cwd=main_repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=main_repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=main_repo, check=True)

    # Create initial commit
    (main_repo / "test.txt").write_text("test")
    subprocess.run(["git", "add", "."], cwd=main_repo, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=main_repo, check=True)

    # Create worktree
    worktree = tmp_path / "worktree"
    subprocess.run(
        ["git", "worktree", "add", str(worktree), "-b", "feature"],
        cwd=main_repo,
        check=True,
        capture_output=True
    )

    # Create task in worktree
    task_dir = worktree / "tasks" / "test_task"
    task_dir.mkdir(parents=True)
    (task_dir / "task.yaml").write_text("""
prompts:
  - key: base
    prompt: "test"
author_name: test
author_email: test@test.com
difficulty: easy
""")

    handler = TrialHandler(
        trial_name="test",
        input_path=task_dir,
        task_key="base"
    )

    # Should point to ade-bench's databases (where code lives)
    # If we're running from agent-install-phase worktree, it should find main ade-bench
    db_path = handler.shared_databases_root_path
    assert db_path.exists()
    # The path should NOT contain ".worktrees" in it (should be main repo)
    assert ".worktrees" not in str(db_path)
    assert db_path.name == "databases"
    assert db_path.parent.name == "shared"


def test_shared_duckdb_path_in_worktree_finds_main_repo_file(tmp_path):
    """Test that shared_duckdb_path finds database files in main ade-bench repo from worktree.

    This test verifies that when running from a worktree (like agent-install-phase),
    shared_duckdb_path correctly resolves to the main ade-bench repo's DuckDB directory
    where actual database files exist, not the worktree's empty copy.
    """
    # Create a task in a temporary directory
    task_dir = tmp_path / "tasks" / "test_task"
    task_dir.mkdir(parents=True)
    (task_dir / "task.yaml").write_text("""
prompts:
  - key: base
    prompt: "test"
author_name: test
author_email: test@test.com
difficulty: easy
""")

    handler = TrialHandler(
        trial_name="test",
        input_path=task_dir,
        task_key="base"
    )

    # Should point to ade-bench's duckdb dir (where database files actually exist)
    duckdb_path = handler.shared_duckdb_path
    assert duckdb_path.exists()

    # Check if we're in a worktree by looking at _shared_path
    from importlib.resources import files
    from pathlib import Path as P
    shared_path = P(str(files('ade_bench'))) / '..' / 'shared'
    is_worktree = '.worktrees' in str(shared_path.resolve())

    if is_worktree:
        # If we're in a worktree, the path should point to main repo (no .worktrees)
        assert ".worktrees" not in str(duckdb_path), \
            f"shared_duckdb_path should point to main repo, not worktree: {duckdb_path}"
        # And it should have actual database files (main repo has databases)
        db_files = list(duckdb_path.glob("*.duckdb"))
        assert len(db_files) > 0, \
            f"shared_duckdb_path should have database files from main repo, found: {db_files}"

    assert duckdb_path.name == "duckdb"
    assert duckdb_path.parent.name == "databases"
    assert duckdb_path.parent.parent.name == "shared"


def test_shared_snowflake_path_uses_root_path(tmp_path):
    """Test that shared_snowflake_path uses shared_databases_root_path.

    This ensures shared_snowflake_path behaves consistently with shared_duckdb_path
    by using shared_databases_root_path instead of shared_databases_path. This makes
    database resolution work correctly in both regular repos and worktrees.
    """
    # Create a task in a temporary directory
    task_dir = tmp_path / "tasks" / "test_task"
    task_dir.mkdir(parents=True)
    (task_dir / "task.yaml").write_text("""
prompts:
  - key: base
    prompt: "test"
author_name: test
author_email: test@test.com
difficulty: easy
""")

    handler = TrialHandler(
        trial_name="test",
        input_path=task_dir,
        task_key="base"
    )

    # shared_snowflake_path should use shared_databases_root_path (like duckdb does)
    # not shared_databases_path (which is worktree-aware)
    expected_path = handler.shared_databases_root_path / "snowflake"

    assert handler.shared_snowflake_path == expected_path, \
        f"shared_snowflake_path should equal shared_databases_root_path/snowflake\n" \
        f"  Expected: {expected_path}\n" \
        f"  Got: {handler.shared_snowflake_path}"

    # Verify it matches the pattern of shared_duckdb_path
    assert handler.shared_duckdb_path == handler.shared_databases_root_path / "duckdb"
    assert handler.shared_snowflake_path == handler.shared_databases_root_path / "snowflake"

    # Both should have the same parent
    assert handler.shared_snowflake_path.parent == handler.shared_duckdb_path.parent


def test_shared_databases_path_is_worktree_aware(tmp_path):
    """Test that shared_databases_path can be worktree-specific (for future use).

    This property uses _shared_path which is worktree-aware. This allows
    for potential future features where non-gitignored database configs
    might be modified per worktree.
    """
    # Setup worktree
    main_repo = tmp_path / "main"
    main_repo.mkdir()
    subprocess.run(["git", "init"], cwd=main_repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=main_repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=main_repo, check=True)

    # Create initial commit
    (main_repo / "test.txt").write_text("test")
    subprocess.run(["git", "add", "."], cwd=main_repo, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=main_repo, check=True)

    # Create worktree
    worktree = tmp_path / "worktree"
    subprocess.run(
        ["git", "worktree", "add", str(worktree), "-b", "feature"],
        cwd=main_repo,
        check=True,
        capture_output=True
    )

    # Create databases dir in worktree
    worktree_db_dir = worktree / "shared" / "databases"
    worktree_db_dir.mkdir(parents=True)

    # Create task in worktree
    task_dir = worktree / "tasks" / "test_task"
    task_dir.mkdir(parents=True)
    (task_dir / "task.yaml").write_text("""
prompts:
  - key: base
    prompt: "test"
author_name: test
author_email: test@test.com
difficulty: easy
""")

    handler = TrialHandler(
        trial_name="test",
        input_path=task_dir,
        task_key="base"
    )

    # shared_databases_path should be worktree-specific
    # This test creates a task in a temporary worktree, but the handler
    # will use the actual code location (from ade_bench package)
    # So we can only verify that the two properties are different
    assert handler.shared_databases_path != handler.shared_databases_root_path

    # shared_databases_root_path should NOT have .worktrees in it
    assert ".worktrees" not in str(handler.shared_databases_root_path)
