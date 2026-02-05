"""
ABOUTME: Tests for FileDiffHandler snapshot and diff operations
ABOUTME: Validates file snapshot capture and path exclusion behavior
"""

import tempfile
from pathlib import Path

import docker
import pytest

from ade_bench.handlers.file_diff_handler import (
    FileDiffHandler,
)


@pytest.fixture
def test_container():
    """Create a test container with sample files."""
    client = docker.from_env()
    container = client.containers.run(
        "alpine:latest",
        command="sleep 60",
        detach=True,
        remove=True,
    )

    # Create test files in container
    container.exec_run(["sh", "-c", "mkdir -p /app/subdir /app/logs /app/.hidden"])
    container.exec_run(["sh", "-c", "echo 'file1 content' > /app/file1.txt"])
    container.exec_run(["sh", "-c", "echo 'file2 content' > /app/subdir/file2.txt"])
    container.exec_run(["sh", "-c", "echo 'log content' > /app/logs/debug.log"])
    container.exec_run(["sh", "-c", "echo 'hidden content' > /app/.hidden/secret.txt"])

    yield container
    container.stop()


@pytest.fixture
def temp_output_dir():
    """Create temporary output directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_capture_snapshot_basic(test_container, temp_output_dir):
    """Test basic snapshot capture without exclusions."""
    handler = FileDiffHandler(
        output_dir=temp_output_dir,
        enabled=True,
        exclude_paths=[],
    )

    snapshot = handler.capture_snapshot(test_container, directory="/app")

    assert snapshot is not None
    assert len(snapshot.files) >= 2  # At least file1.txt and file2.txt
    assert "/app/file1.txt" in snapshot.files
    assert "/app/subdir/file2.txt" in snapshot.files
    assert snapshot.files["/app/file1.txt"] == "file1 content\n"
    assert snapshot.files["/app/subdir/file2.txt"] == "file2 content\n"


def test_capture_snapshot_with_exclusions(test_container, temp_output_dir):
    """Test snapshot capture with path exclusions."""
    handler = FileDiffHandler(
        output_dir=temp_output_dir,
        enabled=True,
        exclude_paths=["/logs", "/.hidden"],
    )

    snapshot = handler.capture_snapshot(test_container, directory="/app")

    assert snapshot is not None
    # Should include normal files
    assert "/app/file1.txt" in snapshot.files
    assert "/app/subdir/file2.txt" in snapshot.files

    # Should exclude files matching patterns
    assert not any("/logs" in path for path in snapshot.files.keys())
    assert not any("/.hidden" in path for path in snapshot.files.keys())


def test_capture_snapshot_excludes_dotfiles_by_default(test_container, temp_output_dir):
    """Test that hidden files (.*) are excluded by find command."""
    handler = FileDiffHandler(
        output_dir=temp_output_dir,
        enabled=True,
        exclude_paths=[],
    )

    snapshot = handler.capture_snapshot(test_container, directory="/app")

    assert snapshot is not None
    # Hidden directories should be excluded by find command
    assert not any("/.hidden" in path for path in snapshot.files.keys())


def test_snapshot_deduplication(test_container, temp_output_dir):
    """Test that content deduplication works correctly."""
    handler = FileDiffHandler(
        output_dir=temp_output_dir,
        enabled=True,
        exclude_paths=[],
    )

    # Create duplicate content
    test_container.exec_run(["sh", "-c", "echo 'same content' > /app/dup1.txt"])
    test_container.exec_run(["sh", "-c", "echo 'same content' > /app/dup2.txt"])

    snapshot = handler.capture_snapshot(test_container, directory="/app")

    assert snapshot is not None
    # Both files should be in snapshot
    assert "/app/dup1.txt" in snapshot.files
    assert "/app/dup2.txt" in snapshot.files

    # Content should be deduplicated in content_manager
    hash1 = snapshot.file_hashes["/app/dup1.txt"]
    hash2 = snapshot.file_hashes["/app/dup2.txt"]
    assert hash1 == hash2  # Same content = same hash

    # Content store should only have one copy
    assert len([h for h in snapshot.content_manager.content_store.keys() if h == hash1]) == 1


def test_create_diff(test_container, temp_output_dir):
    """Test diff creation between snapshots."""
    handler = FileDiffHandler(
        output_dir=temp_output_dir,
        enabled=True,
        exclude_paths=[],
    )

    # Capture initial snapshot
    snapshot1 = handler.capture_snapshot(test_container, directory="/app")

    # Modify files
    test_container.exec_run(["sh", "-c", "echo 'modified content' > /app/file1.txt"])
    test_container.exec_run(["sh", "-c", "echo 'new file' > /app/new.txt"])
    test_container.exec_run(["sh", "-c", "rm /app/subdir/file2.txt"])

    # Capture second snapshot
    snapshot2 = handler.capture_snapshot(test_container, directory="/app")

    # Create diff
    diff = handler.create_diff(snapshot1, snapshot2)

    assert diff is not None
    assert "/app/new.txt" in diff.added_files
    assert "/app/subdir/file2.txt" in diff.removed_files
    assert "/app/file1.txt" in diff.modified_files


def test_should_exclude_path():
    """Test path exclusion logic."""
    handler = FileDiffHandler(
        output_dir=Path("/tmp"),
        enabled=True,
        exclude_paths=["/logs", "/tmp", "node_modules"],
    )

    assert handler._should_exclude_path("/app/logs/debug.log") is True
    assert handler._should_exclude_path("/app/tmp/cache.txt") is True
    assert handler._should_exclude_path("/app/node_modules/pkg/index.js") is True
    assert handler._should_exclude_path("/app/src/main.py") is False
    assert handler._should_exclude_path("/app/file.txt") is False
