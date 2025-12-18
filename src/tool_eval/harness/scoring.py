"""Scoring logic for tool call correctness."""

import json
from typing import Any

from ..client import LMStudioClient


def normalize_value(val: Any) -> Any:
    """Normalize values for comparison."""
    if val is None:
        return None
    if isinstance(val, str):
        # Normalize datetime formats: remove trailing :00 seconds
        if len(val) >= 16 and val[10] == "T" and val.count(":") >= 2:
            # ISO datetime - normalize to T HH:MM format
            return val[:16]
        return val
    return val


def values_match(expected: Any, actual: Any) -> float:
    """Recursively compare values, returning a score 0-1."""
    # Normalize both values
    expected = normalize_value(expected)
    actual = normalize_value(actual)

    # Both None or both missing
    if expected is None and actual is None:
        return 1.0

    # One is None, other is not
    if expected is None or actual is None:
        return 0.0

    # Both are dicts - recurse
    if isinstance(expected, dict) and isinstance(actual, dict):
        return exact_match_score(expected, actual)

    # Both are lists - compare elements
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) == 0 and len(actual) == 0:
            return 1.0
        if len(expected) != len(actual):
            # Different lengths - partial credit based on how many items match
            max_len = max(len(expected), len(actual))
            min_len = min(len(expected), len(actual))
            if min_len == 0:
                return 0.0
            # Score based on matching items
            total_score = 0.0
            for i in range(min_len):
                total_score += values_match(expected[i], actual[i])
            return total_score / max_len

        # Same length - compare each element
        total = 0.0
        for exp_item, act_item in zip(expected, actual):
            total += values_match(exp_item, act_item)
        return total / len(expected)

    # Direct comparison for primitives
    if expected == actual:
        return 1.0

    return 0.0


def exact_match_score(expected: dict[str, Any], actual: dict[str, Any]) -> float:
    """Score based on exact match of arguments.

    Returns 1.0 if all args match exactly, 0.0 otherwise.
    Partial scoring for partial matches.

    Treats missing keys as equivalent to None (for optional params).
    Recursively handles nested objects and lists.
    """
    if not expected and not actual:
        return 1.0
    if not expected or not actual:
        return 0.0

    # Get all keys from both, treating missing as None
    all_keys = set(expected.keys()) | set(actual.keys())
    if not all_keys:
        return 1.0

    total_score = 0.0
    for key in all_keys:
        exp_val = expected.get(key)
        act_val = actual.get(key)

        # Missing in actual but None in expected = match (optional param omitted)
        if key not in actual and exp_val is None:
            total_score += 1.0
        # Missing in expected but present in actual - check if it's a reasonable default
        elif key not in expected and act_val is not None:
            # Penalize extra fields
            total_score += 0.0
        else:
            # Compare values recursively
            total_score += values_match(exp_val, act_val)

    return total_score / len(all_keys)


def semantic_match_score(
    expected: dict[str, Any],
    actual: dict[str, Any],
    client: LMStudioClient | None = None,
) -> float:
    """Score based on semantic equivalence using LLM-as-judge.

    Uses an LLM to determine if the actual args are semantically
    equivalent to expected (e.g., "SF" ≈ "San Francisco").
    """
    if not client:
        # Fall back to exact match if no client provided
        return exact_match_score(expected, actual)

    if not expected and not actual:
        return 1.0
    if not expected or not actual:
        return 0.0

    # Build prompt for LLM judge
    prompt = f"""Compare these two sets of function arguments and determine if they are semantically equivalent.

Expected arguments:
{json.dumps(expected, indent=2)}

Actual arguments:
{json.dumps(actual, indent=2)}

For each key, determine if the values are semantically equivalent (e.g., "SF" and "San Francisco" are equivalent, "NYC" and "New York City" are equivalent).

Respond with ONLY a JSON object in this exact format:
{{"score": <float between 0 and 1>, "reasoning": "<brief explanation>"}}

Where score is:
- 1.0 if all arguments are semantically equivalent
- 0.0 if none match
- Partial score (e.g., 0.5) if some match but not all
"""

    try:
        response = client.simple_completion(
            prompt,
            system_prompt="You are a precise evaluator. Respond only with valid JSON.",
        )

        # Parse the JSON response
        # Handle case where response might have markdown code blocks
        response = response.strip()
        if response.startswith("```"):
            response = response.split("```")[1]
            if response.startswith("json"):
                response = response[4:]
        response = response.strip()

        result = json.loads(response)
        return float(result.get("score", 0))

    except (json.JSONDecodeError, KeyError, ValueError):
        # Fall back to exact match on parse failure
        return exact_match_score(expected, actual)


def tool_selection_score(
    expected_tools: list[str],
    actual_tool: str | None,
    acceptable_tools: list[str] | None = None,
) -> tuple[bool, str]:
    """Score tool selection correctness.

    Args:
        expected_tools: List of expected tool names (usually one)
        actual_tool: The tool actually called
        acceptable_tools: Optional list of acceptable alternatives

    Returns:
        Tuple of (is_correct, reason)
    """
    if not actual_tool:
        return False, "No tool called"

    # Check primary expected tools
    if actual_tool in expected_tools:
        return True, "Exact match"

    # Check acceptable alternatives
    if acceptable_tools and actual_tool in acceptable_tools:
        return True, f"Acceptable alternative: {actual_tool}"

    return False, f"Expected {expected_tools}, got {actual_tool}"


class Scorer:
    """Configurable scorer for tool calls."""

    def __init__(
        self,
        use_semantic: bool = True,
        client: LMStudioClient | None = None,
    ):
        self.use_semantic = use_semantic
        self.client = client

    def score_args(
        self,
        expected: dict[str, Any],
        actual: dict[str, Any],
    ) -> float:
        """Score argument correctness."""
        if self.use_semantic and self.client:
            return semantic_match_score(expected, actual, self.client)
        return exact_match_score(expected, actual)

    def score_tool(
        self,
        expected_tool: str,
        actual_tool: str | None,
        acceptable_tools: list[str] | None = None,
    ) -> tuple[bool, str]:
        """Score tool selection."""
        return tool_selection_score(
            [expected_tool],
            actual_tool,
            acceptable_tools,
        )
