import json
from typing import Dict, Any

from ade_bench.parsers.base_parser import BaseParser


class GeminiParser(BaseParser):
    """Parser for Gemini agent responses to extract runtime, token usage, and cost metrics."""

    def parse(self, content: str) -> Dict[str, Any]:
        """
        Parse Gemini agent response to extract metrics.

        Gemini outputs JSON at the end with format:
        {"response": "...", "stats": {"models": {"gemini-2.5-pro": {"tokens": {...}, "api": {...}}}}}

        Returns a dictionary with the following keys:
        - runtime_ms: totalLatencyMs from api stats
        - input_tokens: prompt tokens (excluding cached)
        - output_tokens: candidates tokens
        - cache_tokens: cached tokens
        - cost_usd: Estimated from https://ai.google.dev/pricing
        - num_turns: totalCalls from tools stats
        - success: Whether the response completed without errors
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
            # Find the last JSON object in the output (the stats)
            # The JSON might have shell prompt appended, so we need to extract it carefully

            # First, try to find where the JSON starts by looking for a line that starts with {
            # and has "stats" in the subsequent content
            lines = content.strip().split("\n")
            json_str = None

            # Try to find a JSON object starting from the end
            for i in range(len(lines) - 1, -1, -1):
                line = lines[i].strip()
                if line.startswith("{"):
                    # Found potential start of JSON, collect the rest
                    potential_json_lines = lines[i:]
                    potential_json = "\n".join(potential_json_lines)

                    # The last line might have shell prompt appended, try to extract just the JSON
                    # Look for the closing brace and ignore anything after it
                    # We need to find the matching closing brace for the opening one
                    brace_count = 0
                    json_end = -1
                    for idx, char in enumerate(potential_json):
                        if char == "{":
                            brace_count += 1
                        elif char == "}":
                            brace_count -= 1
                            if brace_count == 0:
                                json_end = idx + 1
                                break

                    if json_end > 0:
                        potential_json = potential_json[:json_end]

                    try:
                        data = json.loads(potential_json)
                        # Check if it's the stats JSON we're looking for
                        if "stats" in data:
                            json_str = potential_json
                            break
                    except json.JSONDecodeError:
                        continue

            if not json_str:
                # No stats found - check for API error
                # Gemini CLI outputs: "Error when talking to Gemini API Full report available at: /tmp/gemini-client-error-..."
                if "Error when talking to Gemini API" in content:
                    self._logger.warning("Gemini API error detected (quota/rate limit)")
                    default_return["error"] = "quota_exceeded"
                else:
                    self._logger.warning("Could not find Gemini stats JSON in output")
                return default_return

            data = json.loads(json_str)
            stats = data.get("stats", {})
            models_stats = stats.get("models", {})

            # Gemini can use different models, find the one that was used
            total_input_tokens = 0
            total_output_tokens = 0
            total_cache_tokens = 0
            total_latency_ms = 0
            total_num_turns = 0
            total_cost_usd = 0.0
            primary_model_name = None
            max_output_tokens = 0

            for model_name, model_data in models_stats.items():
                tokens = model_data.get("tokens", {})
                api = model_data.get("api", {})

                total_latency_ms += api.get("totalLatencyMs", 0)
                total_num_turns += api.get("totalRequests", 0)

                # Accumulate tokens across all models used
                input_tokens = tokens.get("prompt", 0)
                candidates_tokens = tokens.get("candidates", 0)
                thought_tokens = tokens.get("thought", 0)
                output_tokens = candidates_tokens + thought_tokens
                cached_tokens = tokens.get("cached", 0)

                if "flash" in model_name:
                    input_cost = 0.30 / 1000000
                    output_cost = 2.50 / 1000000
                    cached_cost = 0.03 / 1000000
                else:
                    # These are "Pro" prices
                    input_cost = 2.00 / 1000000
                    output_cost = 10.00 / 1000000
                    cached_cost = 0.20 / 1000000

                cost_usd = (
                    input_cost * input_tokens
                    + output_cost * output_tokens
                    + cached_cost * cached_tokens
                )

                # Input tokens = prompt - cached
                total_input_tokens += input_tokens
                total_output_tokens += output_tokens
                total_cache_tokens += cached_tokens
                total_cost_usd += cost_usd

                # Track the model with the most output tokens as the primary model
                if output_tokens > max_output_tokens:
                    max_output_tokens = output_tokens
                    primary_model_name = model_name

                # Success if we found the stats
                success = True

            return {
                "runtime_ms": total_latency_ms,
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "cache_tokens": total_cache_tokens,
                "cost_usd": total_cost_usd,
                "num_turns": total_num_turns,
                "success": success,
                "error": None,
                "model_name": primary_model_name or "default",
            }

        except Exception as e:
            self._logger.error(f"Error parsing Gemini response: {e}")
            return default_return
