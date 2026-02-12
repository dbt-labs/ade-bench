#!/usr/bin/env python3
"""Script to render file diff logs as beautiful HTML with color coding."""

import json
import re
import sys
from pathlib import Path
from datetime import datetime

# Add the project root to the sys path
sys.path.append(str(Path(__file__).parent.parent))


def find_diff_logs(experiment_dir):
    """Find all file_diff_log.txt files in the experiment directory."""
    return list(Path(experiment_dir).rglob("file_diff_log.txt"))


def load_diff_json(diff_log_path: Path) -> dict:
    """Load the JSON diff data from the corresponding file_diffs.json file."""
    json_path = diff_log_path.parent / "file_diffs.json"
    if not json_path.exists():
        return {}

    try:
        with open(json_path, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load JSON diff data: {e}")
        return {}


def get_file_content(json_data: dict, file_path: str, snapshot_type: str = "after") -> str:
    """Get file content from optimized JSON data structure."""
    if not json_data or "content_manager" not in json_data:
        return ""

    content_manager = json_data["content_manager"]
    content_store = content_manager.get("content_store", {})

    # Look through diffs to find the file in the specified snapshot type
    for diff_data in json_data.get("diffs", []):
        snapshot_data = diff_data.get(snapshot_type, {})
        file_hashes = snapshot_data.get("file_hashes", {})

        # Get the content hash for this file from the snapshot
        content_hash = file_hashes.get(file_path)
        if content_hash:
            return content_store.get(content_hash, "")

    return ""


def parse_diff_log(log_content: str) -> list[dict]:
    """Parse the file diff log content into structured data."""
    phases = []
    current_phase = None

    lines = log_content.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # Look for phase headers
        if line.startswith("=" * 60):
            i += 1
            if i < len(lines) and "FILE DIFF" in lines[i]:
                phase_line = lines[i].strip()
                phase_match = re.search(r"FILE DIFF - (\w+) PHASE", phase_line)
                if phase_match:
                    phase_name = phase_match.group(1).lower()
                    i += 1

                    # Get timestamp
                    timestamp = None
                    if i < len(lines) and lines[i].strip().startswith("Timestamp:"):
                        timestamp_str = lines[i].strip().replace("Timestamp:", "").strip()
                        try:
                            timestamp = datetime.fromisoformat(timestamp_str)
                        except ValueError:
                            pass
                        i += 1

                    # Initialize phase data
                    current_phase = {
                        "name": phase_name,
                        "timestamp": timestamp,
                        "added_files": [],
                        "removed_files": [],
                        "modified_files": [],
                        "unified_diffs": {},
                    }
                    phases.append(current_phase)
                    continue

        # Look for file lists (but don't collect files here - they're listed individually)
        if current_phase and (
            "ADDED FILES" in line or "REMOVED FILES" in line or "MODIFIED FILES" in line
        ):
            # Just skip the header line - files are listed individually with ~ prefix
            pass

        # Look for individual file entries (with +, -, or ~ prefix)
        if current_phase and lines[i].startswith("  + "):
            # This is an added file entry
            file_path = lines[i][4:].strip()  # Remove the '  + ' prefix
            if file_path not in current_phase["added_files"]:
                current_phase["added_files"].append(file_path)
        elif current_phase and lines[i].startswith("  - "):
            # This is a removed file entry
            file_path = lines[i][4:].strip()  # Remove the '  - ' prefix
            if file_path not in current_phase["removed_files"]:
                current_phase["removed_files"].append(file_path)
        elif current_phase and lines[i].startswith("  ~ "):
            # This is a modified file entry
            file_path = lines[i][4:].strip()  # Remove the '  ~ ' prefix
            if file_path not in current_phase["modified_files"]:
                current_phase["modified_files"].append(file_path)

        # Look for unified diff sections
        if current_phase and "UNIFIED DIFF for" in line:
            # Extract file path from the line
            file_path = line.replace("UNIFIED DIFF for", "").strip()
            # Remove trailing colon if present
            if file_path.endswith(":"):
                file_path = file_path[:-1]
            i += 1

            # Collect diff content until we hit the next file or phase
            diff_lines = []
            while i < len(lines):
                current_line = lines[i]
                # Stop if we hit another unified diff, phase separator, or file entry
                # Don't stop at empty lines as they can be part of the diff
                if (
                    "UNIFIED DIFF for" in current_line
                    or current_line.strip().startswith("=" * 60)
                    or current_line.strip().startswith("ADDED FILES")
                    or current_line.strip().startswith("REMOVED FILES")
                    or current_line.strip().startswith("MODIFIED FILES")
                    or current_line.startswith("  ~ ")
                ):
                    break
                diff_lines.append(current_line)
                i += 1

            if diff_lines:
                current_phase["unified_diffs"][file_path] = "\n".join(diff_lines)

        i += 1

    return phases


def generate_html(phases: list[dict], task_id: str = None, json_data: dict = None) -> str:
    """Generate HTML content from parsed diff phases."""
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>File Diff Log{f" - {task_id}" if task_id else ""}</title>
    <style>
        body {{
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            background-color: #1e1e1e;
            color: #d4d4d4;
            margin: 0;
            padding: 10px;
            line-height: 1.2;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}

        h1 {{
            color: #569cd6;
            font-size: 18px;
            margin-bottom: 15px;
            border-bottom: 1px solid #3c3c3c;
            padding-bottom: 8px;
        }}

        .phase {{
            margin-bottom: 20px;
            border: 1px solid #3c3c3c;
            border-radius: 4px;
            overflow: hidden;
        }}

        .phase-header {{
            background-color: #2d2d30;
            padding: 8px 12px;
            cursor: pointer;
            user-select: none;
            display: flex;
            align-items: center;
            justify-content: space-between;
            transition: background-color 0.2s;
        }}

        .phase-header:hover {{
            background-color: #3c3c3c;
        }}

        .phase-header.collapsed .collapse-icon {{
            transform: rotate(-90deg);
        }}

        .phase-stats {{
            margin-top: 4px;
            font-size: 11px;
            color: #9cdcfe;
        }}

        .phase-title {{
            color: #4ec9b0;
            font-size: 14px;
            font-weight: bold;
        }}

        .collapse-icon {{
            color: #9cdcfe;
            font-size: 12px;
            transition: transform 0.2s;
        }}

        .phase-content {{
            background-color: #1e1e1e;
            transition: max-height 0.3s ease, padding 0.3s ease, opacity 0.3s ease;
            overflow: hidden;
        }}

        .phase-content.collapsed {{
            max-height: 0;
            padding: 0;
            opacity: 0;
        }}

        .file-list {{
            margin-bottom: 15px;
        }}

        .file-list-title {{
            color: #569cd6;
            font-size: 12px;
            margin-bottom: 6px;
            font-weight: bold;
        }}

        .file-item {{
            background-color: #2d2d30;
            padding: 4px 8px;
            margin: 2px 0;
            border-radius: 2px;
            font-size: 11px;
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
        }}

        .file-item.added {{
            background-color: rgba(13, 79, 13, 0.3);
            color: #4ec9b0;
        }}

        .file-item.removed {{
            background-color: rgba(79, 13, 13, 0.3);
            color: #f44747;
        }}

        .file-item.modified {{
            background-color: rgba(79, 79, 13, 0.3);
            color: #dcdcaa;
        }}

        .diff-container {{
            margin-top: 15px;
        }}

        .diff-header {{
            background-color: #2d2d30;
            padding: 6px 10px;
            font-size: 11px;
            font-weight: bold;
            color: #569cd6;
            border-bottom: 1px solid #3c3c3c;
        }}

        .diff-content {{
            background-color: #1e1e1e;
            padding: 8px;
            font-size: 10px;
            line-height: 1.1;
            overflow-x: auto;
        }}

        .diff-line {{
            margin: 0;
            padding: 1px 0;
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
        }}

        .diff-line.added {{
            background-color: rgba(13, 79, 13, 0.3);
            color: #4ec9b0;
        }}

        .diff-line.removed {{
            background-color: rgba(79, 13, 13, 0.3);
            color: #f44747;
        }}

        .diff-line.context {{
            color: #9cdcfe;
        }}

        .phase-separator {{
            height: 1px;
            background: linear-gradient(90deg, transparent, #3c3c3c, transparent);
            margin: 15px 0;
        }}

        .no-changes {{
            color: #6a9955;
            font-style: italic;
            text-align: center;
            padding: 20px;
        }}

    </style>
    <script>
        function togglePhase(phaseId) {{
            const header = document.getElementById(phaseId + '-header');
            const content = document.getElementById(phaseId + '-content');

            header.classList.toggle('collapsed');
            content.classList.toggle('collapsed');
        }}
    </script>
</head>
<body>
    <div class="container">
        <h1>File Diff Log{f" - {task_id}" if task_id else ""}</h1>
"""

    # Generate phases
    for i, phase in enumerate(phases):
        phase_id = f"phase-{i}"

        # Calculate stats for this phase
        added_count = len(phase["added_files"])
        removed_count = len(phase["removed_files"])
        modified_count = len(phase["modified_files"])

        # Build stats HTML
        stats_parts = []
        if added_count > 0:
            stats_parts.append(f"Files added: {added_count}")
        if removed_count > 0:
            stats_parts.append(f"Files removed: {removed_count}")
        if modified_count > 0:
            stats_parts.append(f"Files modified: {modified_count}")

        stats_html = " | ".join(stats_parts) if stats_parts else "No changes"

        html += f"""
        <div class="phase">
            <div class="phase-header collapsed" id="{phase_id}-header" onclick="togglePhase('{phase_id}')">
                <div>
                    <div class="phase-title">{phase['name'].title()} Phase</div>
                    <div class="phase-stats">{stats_html}</div>
                </div>
                <div class="collapse-icon">▼</div>
            </div>
            <div class="phase-content collapsed" id="{phase_id}-content">
"""

        # Add file lists with full content for added/removed files
        if added_count > 0:
            html += f"""
                <div class="file-list">
                    <div class="file-list-title">Added Files ({added_count})</div>
"""
            for file_path in phase["added_files"]:
                html += f'                    <div class="file-item added">{file_path}</div>\n'
            html += "                </div>\n"

            # Show full content for added files
            html += '                <div class="diff-container">\n'
            for file_path in phase["added_files"]:
                # Clean the file path (remove + prefix if present)
                clean_file_path = file_path.lstrip("+ ").strip()

                # Get file content from JSON data
                file_content = get_file_content(json_data, clean_file_path, "after")

                if file_content is not None:
                    html += f"""
                    <div class="diff-header">{file_path} (Added)</div>
                    <div class="diff-content">
"""
                    for line in file_content.split("\n"):
                        html += (
                            f'                        <div class="diff-line added">+{line}</div>\n'
                        )
                    html += "                    </div>\n"
            html += "                </div>\n"

        if removed_count > 0:
            html += f"""
                <div class="file-list">
                    <div class="file-list-title">Removed Files ({removed_count})</div>
"""
            for file_path in phase["removed_files"]:
                html += f'                    <div class="file-item removed">{file_path}</div>\n'
            html += "                </div>\n"

            # Show full content for removed files
            html += '                <div class="diff-container">\n'
            for file_path in phase["removed_files"]:
                # Clean the file path (remove - prefix if present)
                clean_file_path = file_path.lstrip("- ").strip()

                # Get file content from JSON data
                file_content = get_file_content(json_data, clean_file_path, "before")

                if file_content is not None:
                    html += f"""
                    <div class="diff-header">{file_path} (Removed)</div>
                    <div class="diff-content">
"""
                    for line in file_content.split("\n"):
                        html += f'                        <div class="diff-line removed">-{line}</div>\n'
                    html += "                    </div>\n"
            html += "                </div>\n"

        if modified_count > 0:
            html += f"""
                <div class="file-list">
                    <div class="file-list-title">Modified Files ({modified_count})</div>
"""
            for file_path in phase["modified_files"]:
                html += f'                    <div class="file-item modified">{file_path}</div>\n'
            html += "                </div>\n"

        # Add unified diffs for modified files only
        if phase["unified_diffs"]:
            # Filter to only show modified files (not added/removed)
            # Clean the modified files list for matching
            clean_modified_files = [f.lstrip("~ ").strip() for f in phase["modified_files"]]
            modified_files_in_diffs = [
                f for f in phase["unified_diffs"].keys() if f in clean_modified_files
            ]

            if modified_files_in_diffs:
                html += '                <div class="diff-container">\n'
                for file_path in modified_files_in_diffs:
                    diff_content = phase["unified_diffs"][file_path]
                    # Skip temporary file headers
                    if (
                        file_path.startswith("--- /tmp")
                        or file_path.startswith("+++ /tmp")
                        or "/var/folders" in file_path
                    ):
                        continue

                    html += f"""
                    <div class="diff-header">{file_path} (Modified)</div>
                    <div class="diff-content">
"""
                    for line in diff_content.split("\n"):
                        # Skip temporary file headers
                        if (
                            line.startswith("--- /tmp")
                            or line.startswith("+++ /tmp")
                            or "/var/folders" in line
                        ):
                            continue
                        # Check for added/removed lines (with optional leading spaces)
                        stripped = line.lstrip()
                        if stripped.startswith("+") and not stripped.startswith("+++"):
                            html += f'                        <div class="diff-line added">{line}</div>\n'
                        elif stripped.startswith("-") and not stripped.startswith("---"):
                            html += f'                        <div class="diff-line removed">{line}</div>\n'
                        else:
                            html += f'                        <div class="diff-line context">{line}</div>\n'
                    html += "                    </div>\n"
                html += "                </div>\n"

        # Show "no changes" message if nothing happened
        if added_count == 0 and removed_count == 0 and modified_count == 0:
            html += (
                '                <div class="no-changes">No changes detected in this phase</div>\n'
            )

        html += "            </div>\n        </div>\n"

        # Add separator between phases (except for the last one)
        if i < len(phases) - 1:
            html += '        <div class="phase-separator"></div>\n'

    html += """
    </div>
</body>
</html>"""

    return html


def render_diff_log_html(diff_log_path: Path, task_id: str = None) -> Path:
    """Render a file diff log as HTML.

    Args:
        diff_log_path: Path to the file_diff_log.txt file
        task_id: Optional task ID to include in the title

    Returns:
        Path to the generated HTML file
    """
    # Read and parse the diff log
    if not diff_log_path.exists():
        raise FileNotFoundError(f"Diff log file not found: {diff_log_path}")

    with open(diff_log_path, "r") as f:
        log_content = f.read()

    phases = parse_diff_log(log_content)

    if not phases:
        raise ValueError("No diff phases found in the log file.")

    # Load JSON data for full file content
    json_data = load_diff_json(diff_log_path)

    # Generate HTML
    html_content = generate_html(phases, task_id, json_data)

    # Return the HTML content instead of writing to file
    # The caller will handle writing to the appropriate location
    return html_content


if __name__ == "__main__":
    # Simple CLI for testing
    import argparse

    parser = argparse.ArgumentParser(description="Render file diff logs as HTML")
    parser.add_argument("diff_log_path", type=Path, help="Path to file_diff_log.txt")
    parser.add_argument("--task-id", help="Task ID for the title")

    args = parser.parse_args()

    try:
        html_content = render_diff_log_html(args.diff_log_path, args.task_id)
        print(html_content)  # Output HTML to stdout for CLI usage
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
