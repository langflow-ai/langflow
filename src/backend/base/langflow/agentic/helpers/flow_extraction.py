"""Flow JSON extraction from LLM markdown output.

Extracts compact flow JSON from free-form LLM responses using a multi-fallback
strategy. LLMs frequently wrap JSON in markdown code fences or surround it with
explanatory text; this module handles all common output patterns robustly.
"""

from __future__ import annotations

import json
import re


def _try_parse_json(text: str) -> dict | None:
    """Attempt to parse text as JSON, returning None on failure."""
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except (json.JSONDecodeError, ValueError):
        pass
    return None


def _fix_common_llm_json_errors(text: str) -> str:
    """Apply heuristic fixes for common LLM JSON formatting mistakes."""
    # Replace Python booleans with JSON booleans
    text = re.sub(r"\bTrue\b", "true", text)
    text = re.sub(r"\bFalse\b", "false", text)
    text = re.sub(r"\bNone\b", "null", text)

    # Remove trailing commas before ] or }
    text = re.sub(r",\s*([}\]])", r"\1", text)

    # Replace single-quoted strings with double-quoted (simple cases)
    # Only when not inside a double-quoted string — use a simple heuristic
    text = re.sub(r"'([^']*)'", r'"\1"', text)

    return text


def _is_valid_compact_flow(data: dict) -> bool:
    """Check that a parsed dict has the minimum structure of a compact flow."""
    if not isinstance(data.get("nodes"), list):
        return False
    if not isinstance(data.get("edges"), list):
        return False
    # Each node must have id and type
    for node in data["nodes"]:
        if not isinstance(node, dict):
            return False
        if not isinstance(node.get("id"), str) or not node["id"]:
            return False
        if not isinstance(node.get("type"), str) or not node["type"]:
            return False
    # Each edge must have the four required fields
    for edge in data["edges"]:
        if not isinstance(edge, dict):
            return False
        for field in ("source", "source_output", "target", "target_input"):
            if not isinstance(edge.get(field), str):
                return False
    return True


def extract_compact_flow(llm_output: str) -> dict | None:
    """Extract compact flow JSON from LLM markdown output.

    Tries multiple extraction strategies in order:
    1. JSON code fence (```json ... ```)
    2. Generic code fence (``` ... ```)
    3. Raw JSON object (outermost { } containing "nodes" key)
    4. Partial recovery (fix common LLM JSON errors, then retry above)

    Args:
        llm_output: Raw text output from the LLM.

    Returns:
        Parsed compact flow dict if extraction succeeds, None otherwise.
    """
    # Strategy 1: ```json ... ``` code fence
    json_fence_pattern = re.compile(r"```json\s*\n(.*?)\n```", re.DOTALL)
    for match in json_fence_pattern.finditer(llm_output):
        candidate = match.group(1).strip()
        parsed = _try_parse_json(candidate)
        if parsed and _is_valid_compact_flow(parsed):
            return parsed

    # Strategy 2: generic ``` ... ``` code fence
    generic_fence_pattern = re.compile(r"```\s*\n(.*?)\n```", re.DOTALL)
    for match in generic_fence_pattern.finditer(llm_output):
        candidate = match.group(1).strip()
        parsed = _try_parse_json(candidate)
        if parsed and _is_valid_compact_flow(parsed):
            return parsed

    # Strategy 3: find outermost { } block(s) containing "nodes"
    # Walk through the string finding balanced { } pairs
    for candidate in _extract_json_objects(llm_output):
        parsed = _try_parse_json(candidate)
        if parsed and _is_valid_compact_flow(parsed):
            return parsed

    # Strategy 4: apply heuristic fixes, then retry all strategies
    fixed_output = _fix_common_llm_json_errors(llm_output)
    if fixed_output != llm_output:
        # Retry code fences on fixed output
        for match in json_fence_pattern.finditer(fixed_output):
            candidate = match.group(1).strip()
            parsed = _try_parse_json(candidate)
            if parsed and _is_valid_compact_flow(parsed):
                return parsed

        for match in generic_fence_pattern.finditer(fixed_output):
            candidate = match.group(1).strip()
            parsed = _try_parse_json(candidate)
            if parsed and _is_valid_compact_flow(parsed):
                return parsed

        for candidate in _extract_json_objects(fixed_output):
            parsed = _try_parse_json(candidate)
            if parsed and _is_valid_compact_flow(parsed):
                return parsed

    return None


def _extract_json_objects(text: str) -> list[str]:
    """Extract all top-level JSON object strings from text using brace matching.

    Returns candidates that contain the word "nodes" (to filter irrelevant objects).
    Prefers longer (more complete) candidates first.
    """
    candidates: list[str] = []
    depth = 0
    start = -1

    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start != -1:
                candidate = text[start : i + 1]
                if '"nodes"' in candidate or "'nodes'" in candidate:
                    candidates.append(candidate)
                start = -1

    # Prefer longer candidates (more likely to be the complete flow JSON)
    candidates.sort(key=len, reverse=True)
    return candidates
