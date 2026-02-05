import json
import re
from typing import Dict, Any

from ade_bench.parsers.base_parser import BaseParser

class MacroParser(BaseParser):
    """Parser for Macro agent responses to extract token usage and cost metrics."""

    def parse(self, content: str) -> Dict[str, Any]:
        """
        Parse Macro agent response to extract metrics.

        Returns a dictionary with the following keys:
        - runtime_ms: Currently set to 0 as not provided in Macro output
        - input_tokens: input_tokens
        - output_tokens: output_tokens
        - cache_tokens: Set to 0 as not provided in Macro output
        - cost_usd: total_cost
        - num_turns: Set to 0 as not provided in Macro output
        - success: Whether the response indicates success (not is_error)
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
            "model_name": "default"
        }
        try:
            # Get lines and remove empty ones
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            lines_to_try = []

            # First, try to find any JSON objects in the content
            for line in lines:
                if line.startswith('{') and line.endswith('}'):
                    lines_to_try.append(line)

            # Add lines from bottom up if no obvious JSON objects found
            if not lines_to_try:
                lines_to_try.extend(reversed(lines))

            # Try parsing each line
            for line in lines_to_try:
                self._logger.debug(f"Trying to parse line: {line}")
                if '{' in line and '}' in line:
                    # Extract json content if surrounded by other text
                    json_match = re.search(r'(\{.*\})', line)
                    if json_match:
                        json_str = json_match.group(1)
                        try:
                            data = json.loads(json_str)
                            return self._parse_json_response(data)
                        except json.JSONDecodeError:
                            continue

            # If we can't parse JSON, return default values
            self._logger.error("Could not find parsable JSON response")
            return default_return

        except Exception as e:
            self._logger.error(f"Error parsing Macro response: {e}")
            return default_return

    def _parse_json_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse the JSON response data to extract metrics."""
        # Runtime is not provided in Macro output, so set to 0
        runtime_ms = data.get("duration_ms", 0)

        # Extract token usage
        usage = data.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)

        # Cache tokens and num_turns are not provided in Macro output, so set to 0
        cache_tokens = 0
        num_turns = data.get("num_turns", 0)

        # Extract cost
        cost_usd = data.get("total_cost", 0.0)

        # Determine success
        success = data.get("is_error", True) == False  # noqa: E712

        # Extract model name if available
        model_name = data.get("model")

        return {
            "runtime_ms": runtime_ms,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_tokens": cache_tokens,
            "cost_usd": cost_usd,
            "num_turns": num_turns,
            "success": success,
            "error": None,
            "model_name": model_name or "default"
        }
