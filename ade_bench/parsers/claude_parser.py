import json
from typing import Dict, Any

from ade_bench.parsers.base_parser import BaseParser


class ClaudeParser(BaseParser):
    """Parser for Claude agent responses to extract runtime, token usage, and cost metrics."""

    def parse(self, content: str) -> Dict[str, Any]:
        """
        Parse Claude agent response to extract metrics.

        Returns a dictionary with the following keys:
        - runtime_ms: The higher of duration_ms and duration_api_ms
        - input_tokens: input_tokens
        - output_tokens: output_tokens
        - cache_tokens: cache_creation_input_tokens + cache_read_input_tokens
        - cost_usd: total_cost_usd
        - num_turns: Number of turns in the conversation
        - success: Whether the response indicates success
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
            # Get lines and remove empty ones
            lines = [line.strip() for line in content.split("\n") if line.strip()]
            lines_to_try = []

            # First, try to find the model name from the system init message
            model_name = None
            for line in lines:
                if line.startswith("{") and line.endswith("}"):
                    try:
                        data = json.loads(line)
                        if data.get("type") == "system" and data.get("subtype") == "init":
                            model_name = data.get("model")
                            break
                    except json.JSONDecodeError:
                        continue

            # Find line after AGENT RESPONSE and add it to the list of lines to try
            agent_response_line = None
            for i, line in enumerate(lines):
                if line.startswith("AGENT RESPONSE:"):
                    if i + 1 < len(lines):
                        agent_response_line = lines[i + 1]
                        lines_to_try.append(agent_response_line)
                        break

            # Add lines from bottom up
            lines_to_try.extend(reversed(lines))

            # Try parsing each line for the result message
            for line in lines_to_try:
                self._logger.debug(f"Trying to parse line: {line}")
                if line.startswith("{") and line.endswith("}"):
                    try:
                        data = json.loads(line)
                        result = self._parse_json_response(data, model_name)
                        return result
                    except json.JSONDecodeError:
                        continue

            # If we can't parse JSON, return default values
            self._logger.error("Could not find parsable JSON response")
            return default_return

        except Exception as e:
            self._logger.error(f"Error parsing Claude response: {e}")
            return default_return

    def _parse_json_response(
        self, data: Dict[str, Any], model_name: str | None = None
    ) -> Dict[str, Any]:
        """Parse the JSON response data to extract metrics."""
        # Extract runtime - use the higher of duration_ms and duration_api_ms
        duration_ms = data.get("duration_ms", 0)
        duration_api_ms = data.get("duration_api_ms", 0)
        runtime_ms = max(duration_ms, duration_api_ms)

        # Extract token usage
        usage = data.get("usage", {})
        input_tokens = usage.get("input_tokens", 0) + usage.get("cache_creation_input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        cache_tokens = usage.get("cache_read_input_tokens", 0)

        # Extract number of turns
        num_turns = data.get("num_turns", 0)

        # Extract cost
        cost_usd = data.get("total_cost_usd", 0.0)

        # Determine success
        success = data.get("is_error", True) == False  # noqa: E712

        # If model_name not provided from init message, try to get from modelUsage
        # modelUsage contains a dict of model names to their usage stats
        if model_name is None:
            model_usage = data.get("modelUsage", {})
            if model_usage:
                # Get the model with the highest output tokens (primary model)
                primary_model = max(
                    model_usage.keys(),
                    key=lambda m: model_usage[m].get("outputTokens", 0),
                    default=None,
                )
                model_name = primary_model

        return {
            "runtime_ms": runtime_ms,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_tokens": cache_tokens,
            "cost_usd": cost_usd,
            "num_turns": num_turns,
            "success": success,
            "error": None,
            "model_name": model_name or "default",
        }
