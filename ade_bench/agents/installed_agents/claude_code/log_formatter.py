"""
Log formatter for Claude Code agent.

This module provides parsing and formatting utilities for Claude Code agent
log files (JSON-lines format), and generates HTML transcripts using
claude-code-transcripts.
"""

import contextlib
import io
import json
import logging
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from ade_bench.agents.log_formatter import LogFormatter

logger = logging.getLogger(__name__)


class ClaudeCodeLogFormatter(LogFormatter):
    """Log formatter for Claude Code agent JSON-lines format."""

    @staticmethod
    def strip_ansi_codes(text: str) -> str:
        """Remove ANSI color codes from text."""
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)

    @staticmethod
    def extract_jsonl_content(log_path: Path, inject_prompt: str | None = None) -> str:
        """
        Extract only the JSON lines from a log file that may contain mixed content.

        The log file may contain terminal output before the JSON lines begin.
        This method extracts only valid JSON lines.

        Claude Code's stream-json output doesn't include the initial user prompt,
        only the assistant responses and tool results. If no user prompt with text
        is found in the log, a synthetic one is injected so that transcript
        generation tools can identify conversation boundaries.

        Args:
            log_path: Path to the log file
            inject_prompt: Optional prompt text to inject if none found

        Returns:
            String containing only the JSON lines, newline-separated
        """
        json_lines = []
        has_user_text_prompt = False

        with open(log_path, 'r') as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith('{'):
                    try:
                        # Validate it's actually JSON
                        data = json.loads(stripped)
                        json_lines.append(stripped)

                        # Check if this is a user message with actual text content
                        if data.get('type') == 'user':
                            content = data.get('message', {}).get('content', [])
                            if isinstance(content, str) and content.strip():
                                has_user_text_prompt = True
                            elif isinstance(content, list):
                                for item in content:
                                    if isinstance(item, dict) and item.get('type') == 'text':
                                        has_user_text_prompt = True
                                        break
                    except json.JSONDecodeError:
                        continue

        # If no user prompt found, inject a synthetic one at the beginning
        if not has_user_text_prompt and json_lines:
            prompt_text = inject_prompt or "Claude Code Agent Session"
            synthetic_prompt = json.dumps({
                "type": "user",
                "timestamp": "",
                "message": {
                    "role": "user",
                    "content": prompt_text
                }
            })
            json_lines.insert(0, synthetic_prompt)

        return '\n'.join(json_lines)

    @staticmethod
    def format_tool_input(tool_name: str, tool_input: Dict[str, Any]) -> str:
        """Format tool input parameters nicely."""
        if not tool_input:
            return ""

        lines = []
        for key, value in tool_input.items():
            if isinstance(value, str) and len(value) > 100:
                # Truncate long string values
                lines.append(f"  {key}: {value[:100]}...")
            else:
                lines.append(f"  {key}: {value}")
        return "\n".join(lines)

    @staticmethod
    def format_tool_result(result: Any, max_lines: int = 50) -> str:
        """Format tool result output, limiting length."""
        if isinstance(result, dict):
            # Handle different result formats
            if 'content' in result:
                content = result['content']
            elif 'stdout' in result:
                content = result['stdout']
                if result.get('stderr'):
                    content += f"\n[STDERR]\n{result['stderr']}"
            elif 'filenames' in result:
                content = f"Found {result.get('numFiles', len(result['filenames']))} files:\n"
                content += "\n".join(result['filenames'][:20])
                if result.get('truncated'):
                    content += "\n... (truncated)"
                return content
            elif 'file' in result:
                content = result['file'].get('content', str(result))
            else:
                content = str(result)
        else:
            content = str(result)

        # Strip ANSI codes
        content = ClaudeCodeLogFormatter.strip_ansi_codes(content)

        # Limit length
        lines = content.split('\n')
        if len(lines) > max_lines:
            lines = lines[:max_lines] + [f"\n... ({len(lines) - max_lines} more lines)"]

        return '\n'.join(lines)

    def parse_log_file(self, log_path: Path) -> List[Dict[str, Any]]:
        """Parse the Claude Code agent log file and extract structured information."""
        turns = []
        current_turn = None
        turn_number = 0

        with open(log_path, 'r') as f:
            for line in f:
                # Skip lines that aren't JSON (terminal output, etc.)
                if not line.strip().startswith('{'):
                    continue

                try:
                    data = json.loads(line.strip())
                except json.JSONDecodeError:
                    continue

                msg_type = data.get('type')

                if msg_type == 'system':
                    # System initialization - could be start of session
                    continue

                elif msg_type == 'assistant':
                    message = data.get('message', {})
                    content = message.get('content', [])

                    for item in content:
                        if item.get('type') == 'text':
                            # Assistant message/thinking
                            if current_turn is None or current_turn['tools']:
                                # Start new turn if we have pending tools or no current turn
                                turn_number += 1
                                current_turn = {
                                    'turn': turn_number,
                                    'thinking': [],
                                    'tools': [],
                                    'results': []
                                }
                                turns.append(current_turn)

                            current_turn['thinking'].append(item['text'])

                        elif item.get('type') == 'tool_use':
                            # Tool invocation
                            if current_turn is None:
                                turn_number += 1
                                current_turn = {
                                    'turn': turn_number,
                                    'thinking': [],
                                    'tools': [],
                                    'results': []
                                }
                                turns.append(current_turn)

                            current_turn['tools'].append({
                                'id': item['id'],
                                'name': item['name'],
                                'input': item.get('input', {})
                            })

                elif msg_type == 'user':
                    # Tool results
                    if current_turn is None:
                        continue

                    message = data.get('message', {})
                    content = message.get('content', [])

                    for item in content:
                        if item.get('type') == 'tool_result':
                            tool_id = item.get('tool_use_id')
                            result_content = item.get('content', '')
                            is_error = item.get('is_error', False)

                            # Try to get more detailed result from tool_use_result
                            tool_result = data.get('tool_use_result')

                            current_turn['results'].append({
                                'tool_id': tool_id,
                                'content': result_content,
                                'is_error': is_error,
                                'detailed_result': tool_result
                            })

        return turns

    def format_readable_log(self, turns: List[Dict[str, Any]]) -> str:
        """Format the parsed turns into a readable text string."""
        output = io.StringIO()

        output.write("=" * 80 + "\n")
        output.write("CLAUDE CODE AGENT INTERACTION LOG\n")
        output.write("=" * 80 + "\n\n")

        for turn in turns:
            output.write("\n" + "=" * 80 + "\n")
            output.write(f"TURN {turn['turn']}\n")
            output.write("=" * 80 + "\n\n")

            # Write thinking/messages
            if turn['thinking']:
                output.write("--- ASSISTANT MESSAGE ---\n")
                for thought in turn['thinking']:
                    output.write(f"{thought}\n")
                output.write("\n")

            # Write tools used
            if turn['tools']:
                output.write("--- TOOLS USED ---\n")
                for i, tool in enumerate(turn['tools'], 1):
                    output.write(f"\n[{i}] {tool['name']}\n")
                    tool_input = self.format_tool_input(tool['name'], tool['input'])
                    if tool_input:
                        output.write(f"{tool_input}\n")
                output.write("\n")

            # Write tool results
            if turn['results']:
                output.write("--- TOOL RESULTS ---\n")
                for i, result in enumerate(turn['results'], 1):
                    # Match tool by position if possible
                    tool_name = turn['tools'][i-1]['name'] if i <= len(turn['tools']) else "Unknown"

                    output.write(f"\n[{i}] {tool_name} Result:\n")

                    if result['is_error']:
                        output.write("*** ERROR ***\n")

                    # Use detailed result if available
                    if result['detailed_result']:
                        formatted = self.format_tool_result(result['detailed_result'])
                    else:
                        formatted = self.format_tool_result(result['content'])

                    output.write(f"{formatted}\n")
                output.write("\n")

        output.write("\n" + "=" * 80 + "\n")
        output.write("END OF LOG\n")
        output.write("=" * 80 + "\n")

        return output.getvalue()

    def generate_html_transcript(self, log_path: Path, output_path: Path) -> Path | None:
        """
        Generate an HTML transcript using claude-code-transcripts.

        This method extracts JSON lines from the log file (which may contain
        mixed terminal output and JSON) and uses claude-code-transcripts to
        generate a clean HTML transcript at the specified output path.

        Args:
            log_path: Path to the log file (may contain mixed content)
            output_path: Desired output file path (e.g., sessions/transcript.html)

        Returns:
            Path to the generated HTML file, or None if generation failed
        """
        if not log_path.exists():
            logger.warning(f"Log file not found: {log_path}")
            return None

        try:
            import shutil
            from claude_code_transcripts import generate_html

            # Extract only JSON lines from the log file
            jsonl_content = self.extract_jsonl_content(log_path)
            if not jsonl_content:
                logger.warning(f"No JSON content found in {log_path}")
                return None

            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Use a temporary directory for claude-code-transcripts output,
            # then copy the result to the single well-known output path
            with tempfile.TemporaryDirectory() as tmp_output_dir:
                tmp_output = Path(tmp_output_dir)

                with tempfile.NamedTemporaryFile(
                    mode='w', suffix='.jsonl', delete=False
                ) as tmp_file:
                    tmp_file.write(jsonl_content)
                    tmp_path = Path(tmp_file.name)

                try:
                    # Generate HTML transcript (suppress stdout/stderr from library)
                    with contextlib.redirect_stdout(io.StringIO()), \
                         contextlib.redirect_stderr(io.StringIO()):
                        generate_html(tmp_path, tmp_output)

                    # Find the generated file (index.html or page-001.html)
                    generated = None
                    for candidate in ["index.html", "page-001.html"]:
                        candidate_path = tmp_output / candidate
                        if candidate_path.exists():
                            generated = candidate_path
                            break

                    if generated is None:
                        logger.warning(f"No HTML output found in {tmp_output}")
                        return None

                    # Copy to the well-known output path
                    shutil.copy2(generated, output_path)
                    return output_path
                finally:
                    tmp_path.unlink(missing_ok=True)

        except ImportError:
            logger.warning(
                "claude-code-transcripts not installed. "
                "Install with: pip install claude-code-transcripts"
            )
            return None
        except Exception as e:
            logger.warning(f"Transcript generation failed: {e}")
            return None
