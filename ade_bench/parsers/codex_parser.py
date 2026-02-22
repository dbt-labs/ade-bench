import json
from typing import Dict, Any

from ade_bench.parsers.base_parser import BaseParser


class CodexParser(BaseParser):
    """Parser for Codex agent responses to extract runtime, token usage, and cost metrics."""

    def parse(self, content: str) -> Dict[str, Any]:
        """
        Parse Codex agent response to extract metrics.

        Codex outputs JSON lines with format:
        {"type":"turn.completed","usage":{"input_tokens":N,"cached_input_tokens":N,"output_tokens":N}}

        Returns a dictionary with the following keys:
        - runtime_ms: 0 (not provided by Codex)
        - input_tokens: input_tokens (excluding cached)
        - output_tokens: output_tokens
        - cache_tokens: cached_input_tokens
        - cost_usd: Estimated from https://openai.com/api/pricing/
        - num_turns: Number of item.completed events
        - success: Whether the response completed without errors
        - error: Error string if an error was detected (e.g. "quota_exceeded")
        """

        default_return = {
            "runtime_ms": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_tokens": 0,
            "cost_usd": 0.0,
            "num_turns": 0,
            "success": False,
            "error": None,
            "model_name": "default",
        }

        try:
            # Split content into lines and parse JSON lines
            lines = content.strip().split("\n")

            total_input_tokens = 0
            total_output_tokens = 0
            total_cache_tokens = 0
            cost_usd = 0.0
            num_items = 0
            success = False
            error = None

            for line in lines:
                line = line.strip()
                if not line or not line.startswith("{"):
                    continue

                try:
                    data = json.loads(line)

                    if data.get("type") == "item.completed":
                        num_items += 1

                    # Check for errors in turn.failed events
                    if data.get("type") == "turn.failed":
                        error_data = data.get("error", {})
                        error_message = error_data.get("message", "")
                        if "Quota exceeded" in error_message or "quota" in error_message.lower():
                            error = "quota_exceeded"

                    # Also check for error type messages
                    if data.get("type") == "error":
                        error_message = data.get("message", "")
                        if "Quota exceeded" in error_message or "quota" in error_message.lower():
                            error = "quota_exceeded"

                    # Look for turn.completed events which contain usage data
                    if data.get("type") == "turn.completed":
                        success = True

                        usage = data.get("usage", {})
                        # input_tokens excludes cached tokens
                        total_input_tokens += usage.get("input_tokens", 0)
                        total_cache_tokens += usage.get("cached_input_tokens", 0)
                        total_output_tokens += usage.get("output_tokens", 0)

                        # Cost is estimated from https://openai.com/api/pricing/
                        cost_usd = (
                            (total_input_tokens / 1000000) * 1.25
                            + (total_output_tokens / 1000000) * 10
                            + (total_cache_tokens / 1000000) * 0.125
                        )

                except json.JSONDecodeError:
                    # Skip non-JSON lines
                    continue

            return {
                "runtime_ms": 0,
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "cache_tokens": total_cache_tokens,
                "cost_usd": cost_usd,
                "num_turns": num_items,
                "success": success,
                "error": error,
                "model_name": "default",
            }

        except Exception as e:
            self._logger.error(f"Error parsing Codex response: {e}")
            return default_return
