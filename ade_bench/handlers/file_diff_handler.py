"""File diffing handler for tracking file changes during test execution."""

import hashlib
import io
import json
import subprocess
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ade_bench.utils.logger import logger, log_harness_info


class FileContentManager:
    """Manages file content storage with deduplication using content hashing."""

    def __init__(self):
        self.content_store: Dict[str, str] = {}  # content_hash -> file_content

    def add_file_content(self, file_path: str, content: str) -> str:
        """Add file content and return its hash."""
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        self.content_store[content_hash] = content
        return content_hash

    def get_content_by_hash(self, content_hash: str) -> Optional[str]:
        """Get file content by hash."""
        return self.content_store.get(content_hash)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {"content_store": self.content_store}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FileContentManager":
        """Create from dictionary."""
        manager = cls()
        manager.content_store = data.get("content_store", {})
        return manager


class FileSnapshot:
    """Represents a snapshot of files in a directory at a specific point in time."""

    def __init__(
        self,
        timestamp: datetime,
        directory: str,
        files: Dict[str, str],
        content_manager: FileContentManager,
    ):
        self.timestamp = timestamp
        self.directory = directory
        self.files = files  # file_path -> file_content
        self.content_manager = content_manager

        # Store file hashes instead of content for optimization
        self.file_hashes = {}
        for file_path, content in files.items():
            self.file_hashes[file_path] = content_manager.add_file_content(file_path, content)

    def get_file_content(self, file_path: str) -> Optional[str]:
        """Get file content by path."""
        content_hash = self.file_hashes.get(file_path)
        if content_hash:
            return self.content_manager.get_content_by_hash(content_hash)
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert snapshot to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "directory": self.directory,
            "file_hashes": self.file_hashes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], content_manager: FileContentManager) -> "FileSnapshot":
        """Create snapshot from dictionary."""
        snapshot = cls.__new__(cls)
        snapshot.timestamp = datetime.fromisoformat(data["timestamp"])
        snapshot.directory = data["directory"]
        snapshot.file_hashes = data["file_hashes"]
        snapshot.content_manager = content_manager
        # Reconstruct files dict from hashes
        snapshot.files = {}
        for file_path, content_hash in snapshot.file_hashes.items():
            content = content_manager.get_content_by_hash(content_hash)
            if content is not None:
                snapshot.files[file_path] = content
        return snapshot


class FileDiff:
    """Represents the differences between two file snapshots."""

    def __init__(self, before: FileSnapshot, after: FileSnapshot):
        self.before = before
        self.after = after
        self.added_files: List[str] = []
        self.removed_files: List[str] = []
        self.modified_files: List[str] = []
        self._compute_diff()

    def _compute_diff(self):
        """Compute the differences between the two snapshots."""
        before_files = set(self.before.files.keys())
        after_files = set(self.after.files.keys())

        self.added_files = sorted(after_files - before_files)
        self.removed_files = sorted(before_files - after_files)

        common_files = before_files & after_files
        for file_path in common_files:
            if self.before.files[file_path] != self.after.files[file_path]:
                self.modified_files.append(file_path)

        self.modified_files.sort()

    def get_unified_diff(self, file_path: str) -> Optional[str]:
        """Get unified diff for a specific file."""
        if file_path not in self.modified_files:
            return None

        try:
            # Get file contents from snapshots
            before_content = self.before.get_file_content(file_path)
            after_content = self.after.get_file_content(file_path)

            if before_content is None or after_content is None:
                return None

            # Create temporary files for diff
            with tempfile.NamedTemporaryFile(
                mode="w", delete=False, suffix=".before"
            ) as before_file:
                before_file.write(before_content)
                before_path = before_file.name

            with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".after") as after_file:
                after_file.write(after_content)
                after_path = after_file.name

            # Run diff command
            result = subprocess.run(
                ["diff", "-u", before_path, after_path], capture_output=True, text=True
            )

            # Clean up temp files
            Path(before_path).unlink()
            Path(after_path).unlink()

            if result.returncode == 0:
                return None  # No differences
            elif result.returncode == 1:
                return result.stdout
            else:
                logger.warning(f"Diff command failed for {file_path}: {result.stderr}")
                return None

        except Exception as e:
            logger.error(f"Error generating diff for {file_path}: {e}")
            return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert diff to dictionary for serialization."""
        return {
            "before": self.before.to_dict(),
            "after": self.after.to_dict(),
            "added_files": self.added_files,
            "removed_files": self.removed_files,
            "modified_files": self.modified_files,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], content_manager: FileContentManager) -> "FileDiff":
        """Create diff from dictionary."""
        diff = cls.__new__(cls)
        diff.before = FileSnapshot.from_dict(data["before"], content_manager)
        diff.after = FileSnapshot.from_dict(data["after"], content_manager)
        diff.added_files = data["added_files"]
        diff.removed_files = data["removed_files"]
        diff.modified_files = data["modified_files"]
        return diff


class FileDiffHandler:
    """Handles file diffing operations for test execution."""

    def __init__(
        self,
        output_dir: Path,
        enabled: bool = True,
        exclude_paths: List[str] = None,
        task_name: str = "FILE_DIFF",
    ):
        self.output_dir = output_dir
        self.enabled = enabled
        self.exclude_paths = exclude_paths or []
        self.task_name = task_name
        self.snapshots: List[FileSnapshot] = []
        self.diffs: List[FileDiff] = []
        self.content_manager = FileContentManager()
        self._logger = logger.getChild(__name__)

        if self.enabled:
            # Create diffs folder
            self.diffs_dir = self.output_dir / "diffs"
            self.diffs_dir.mkdir(exist_ok=True)

            self.diff_log_path = self.diffs_dir / "file_diffs.json"
            self.diff_summary_path = self.diffs_dir / "file_diff_summary.txt"

    def _should_exclude_path(self, file_path: str) -> bool:
        """Check if a file path should be excluded from diffing."""
        for exclude_pattern in self.exclude_paths:
            if exclude_pattern in file_path:
                return True
        return False

    def capture_snapshot(self, container, directory: str = "/app") -> Optional[FileSnapshot]:
        """Capture a snapshot of files in the container directory using tar archive."""
        if not self.enabled:
            return None

        try:
            # Get directory contents as tar archive (single API call)
            stream, stat = container.get_archive(directory)

            # Read tar archive into memory
            tar_data = io.BytesIO()
            for chunk in stream:
                tar_data.write(chunk)
            tar_data.seek(0)

            # Extract files from tar archive
            files = {}
            with tarfile.open(fileobj=tar_data, mode="r") as tar:
                for member in tar.getmembers():
                    # Skip directories
                    if not member.isfile():
                        continue

                    # Get full path (tar includes directory name in path)
                    file_path = f"/{member.name}"

                    # Skip hidden files (files starting with .)
                    # This matches the behavior of: find directory -type f -not -path "*/.*"
                    path_parts = member.name.split("/")
                    if any(part.startswith(".") for part in path_parts):
                        continue

                    # Apply exclusion filters
                    if self._should_exclude_path(file_path):
                        self._logger.debug(f"Excluding file from diff: {file_path}")
                        continue

                    # Extract file content
                    try:
                        file_obj = tar.extractfile(member)
                        if file_obj:
                            content = file_obj.read().decode("utf-8")
                            files[file_path] = content
                    except Exception as e:
                        self._logger.debug(f"Could not read file {file_path}: {e}")

            snapshot = FileSnapshot(
                timestamp=datetime.now(),
                directory=directory,
                files=files,
                content_manager=self.content_manager,
            )

            self.snapshots.append(snapshot)
            self._logger.debug(f"Captured snapshot with {len(files)} files from {directory}")
            return snapshot

        except Exception as e:
            self._logger.error(f"Error capturing file snapshot: {e}")
            return None

    def create_diff(
        self, before_snapshot: FileSnapshot, after_snapshot: FileSnapshot
    ) -> Optional[FileDiff]:
        """Create a diff between two snapshots."""
        if not self.enabled:
            return None

        try:
            diff = FileDiff(before_snapshot, after_snapshot)
            self.diffs.append(diff)

            self._logger.debug(
                f"Created diff: {len(diff.added_files)} added, "
                f"{len(diff.removed_files)} removed, "
                f"{len(diff.modified_files)} modified files"
            )

            return diff

        except Exception as e:
            self._logger.error(f"Error creating file diff: {e}")
            return None

    def save_diff_log(self):
        """Save the diff log to file."""
        if not self.enabled or not self.diffs:
            return

        try:
            # Save detailed diff data as JSON with optimized structure
            diff_data = {
                "content_manager": self.content_manager.to_dict(),
                "snapshots": [snapshot.to_dict() for snapshot in self.snapshots],
                "diffs": [diff.to_dict() for diff in self.diffs],
            }

            self.diff_log_path.write_text(json.dumps(diff_data, indent=2))

            # Save human-readable summary
            self._save_diff_summary()

        except Exception as e:
            self._logger.error(f"Error saving diff log: {e}")

    def _save_diff_summary(self):
        """Save a human-readable summary of file changes."""
        if not self.diffs:
            return

        summary_lines = []
        summary_lines.append("FILE DIFF SUMMARY")
        summary_lines.append("=" * 50)
        summary_lines.append("")

        for i, diff in enumerate(self.diffs, 1):
            summary_lines.append(
                f"DIFF {i}: {diff.before.timestamp.strftime('%H:%M:%S')} -> {diff.after.timestamp.strftime('%H:%M:%S')}"
            )
            summary_lines.append("-" * 40)

            if diff.added_files:
                summary_lines.append(f"ADDED FILES ({len(diff.added_files)}):")
                for file_path in diff.added_files:
                    summary_lines.append(f"  + {file_path}")
                summary_lines.append("")

            if diff.removed_files:
                summary_lines.append(f"REMOVED FILES ({len(diff.removed_files)}):")
                for file_path in diff.removed_files:
                    summary_lines.append(f"  - {file_path}")
                summary_lines.append("")

            if diff.modified_files:
                summary_lines.append(f"MODIFIED FILES ({len(diff.modified_files)}):")
                for file_path in diff.modified_files:
                    summary_lines.append(f"  ~ {file_path}")
                summary_lines.append("")

            if not any([diff.added_files, diff.removed_files, diff.modified_files]):
                summary_lines.append("No file changes detected.")
                summary_lines.append("")

            summary_lines.append("")

        self.diff_summary_path.write_text("\n".join(summary_lines))

    def get_latest_snapshot(self) -> Optional[FileSnapshot]:
        """Get the most recent snapshot."""
        return self.snapshots[-1] if self.snapshots else None

    def get_snapshot_count(self) -> int:
        """Get the number of snapshots captured."""
        return len(self.snapshots)

    def get_diff_count(self) -> int:
        """Get the number of diffs created."""
        return len(self.diffs)

    @classmethod
    def load_from_file(cls, diff_log_path: Path) -> Optional["FileDiffHandler"]:
        """Load FileDiffHandler from an optimized diff log file."""
        if not diff_log_path.exists():
            return None

        try:
            with open(diff_log_path, "r") as f:
                data = json.load(f)

            # Create handler instance
            handler = cls.__new__(cls)
            handler.enabled = True
            handler.snapshots = []
            handler.diffs = []

            # Load content manager
            handler.content_manager = FileContentManager.from_dict(data["content_manager"])

            # Load snapshots
            for snapshot_data in data["snapshots"]:
                snapshot = FileSnapshot.from_dict(snapshot_data, handler.content_manager)
                handler.snapshots.append(snapshot)

            # Load diffs
            for diff_data in data["diffs"]:
                diff = FileDiff.from_dict(diff_data, handler.content_manager)
                handler.diffs.append(diff)

            return handler

        except Exception as e:
            logger.error(f"Error loading diff log from {diff_log_path}: {e}")
            return None

    def handle_phase_diffing(self, container, phase: str, task_id: str, logger) -> None:
        """Handle file diffing operations for a specific phase."""
        if not self.enabled:
            return

        # Capture snapshot
        snapshot_count = self.get_snapshot_count()
        if snapshot_count == 0:
            snapshot_type = "initial snapshot"
        elif snapshot_count == 1:
            snapshot_type = "snapshot after migration and setup scripts"
        elif snapshot_count == 2:
            snapshot_type = "snapshot of agent output"
        else:
            snapshot_type = "snapshot"

        log_harness_info(self._logger, self.task_name, phase, f"Capturing {snapshot_type}...")
        snapshot = self.capture_snapshot(container)
        log_harness_info(self._logger, self.task_name, phase, f"Captured {snapshot_type}.")

        if snapshot and self.get_snapshot_count() >= 2:
            # Create diff with previous snapshot
            log_harness_info(self._logger, self.task_name, phase, f"Diffing the {phase} changes...")
            diff = self.create_diff(self.snapshots[-2], self.snapshots[-1])
            if diff:
                diff_summary = f"Captured {phase} diffs: {len(diff.added_files)} added, {len(diff.removed_files)} removed, {len(diff.modified_files)} modified files"
                log_harness_info(self._logger, self.task_name, phase, diff_summary)

                # Save detailed diff info to trial log
                self._save_diff_to_trial_log(phase, diff)

    def _save_diff_to_trial_log(self, phase: str, diff) -> None:
        """Save detailed diff information to the trial log file."""
        try:
            log_file = self.diffs_dir / "file_diff_log.txt"

            with open(log_file, "a") as f:
                f.write(f"\n{'='*60}\n")
                f.write(f"FILE DIFF - {phase.upper()} PHASE\n")
                f.write(f"Timestamp: {diff.after.timestamp}\n")
                f.write(f"{'='*60}\n\n")

                if diff.added_files:
                    f.write(f"ADDED FILES ({len(diff.added_files)}):\n")
                    for file_path in diff.added_files:
                        f.write(f"  + {file_path}\n")
                    f.write("\n")

                if diff.removed_files:
                    f.write(f"REMOVED FILES ({len(diff.removed_files)}):\n")
                    for file_path in diff.removed_files:
                        f.write(f"  - {file_path}\n")
                    f.write("\n")

                if diff.modified_files:
                    f.write(f"MODIFIED FILES ({len(diff.modified_files)}):\n")
                    for file_path in diff.modified_files:
                        f.write(f"  ~ {file_path}\n")

                        # Get and save the unified diff for this file
                        unified_diff = diff.get_unified_diff(file_path)
                        if unified_diff:
                            f.write(f"\n  UNIFIED DIFF for {file_path}:\n")
                            f.write("  " + "\n  ".join(unified_diff.split("\n")) + "\n")
                    f.write("\n")

                if not any([diff.added_files, diff.removed_files, diff.modified_files]):
                    f.write("No file changes detected.\n\n")

                f.write(f"{'='*60}\n")

        except Exception as e:
            self._logger.error(f"Error saving diff to trial log: {e}")
