"""Code and data extraction from markdown responses."""

import json
import logging
import re

logger = logging.getLogger(__name__)

PYTHON_CODE_BLOCK_PATTERN = r"```python\s*([\s\S]*?)```"
FLOW_JSON_BLOCK_PATTERN = r"```flow_json\s*([\s\S]*?)```"
GENERIC_CODE_BLOCK_PATTERN = r"```\s*([\s\S]*?)```"
UNCLOSED_PYTHON_BLOCK_PATTERN = r"```python\s*([\s\S]*)$"
UNCLOSED_GENERIC_BLOCK_PATTERN = r"```\s*([\s\S]*)$"
ANY_CODE_BLOCK_PATTERN = r"```[\s\S]*?```|```[\s\S]*$"


def extract_python_code(text: str) -> str | None:
    """Extract Python code from markdown code blocks.

    Handles both closed (```python ... ```) and unclosed blocks.
    Returns the first code block that appears to be a Langflow component.
    """
    matches = _find_code_blocks(text)
    if not matches:
        return None

    return _find_component_code(matches) or matches[0].strip()


def _find_code_blocks(text: str) -> list[str]:
    """Find all code blocks in text, handling both closed and unclosed blocks."""
    matches = re.findall(PYTHON_CODE_BLOCK_PATTERN, text, re.IGNORECASE)
    if matches:
        return matches

    matches = re.findall(GENERIC_CODE_BLOCK_PATTERN, text)
    if matches:
        return matches

    return _find_unclosed_code_block(text)


def _find_unclosed_code_block(text: str) -> list[str]:
    """Handle LLM responses that don't close the code block with ```."""
    for pattern in [UNCLOSED_PYTHON_BLOCK_PATTERN, UNCLOSED_GENERIC_BLOCK_PATTERN]:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            code = match.group(1).rstrip("`").strip()
            return [code] if code else []

    return []


def _find_component_code(matches: list[str]) -> str | None:
    """Find the first match that looks like a Langflow component."""
    for match in matches:
        if "class " in match and "Component" in match:
            return match.strip()
    return None


# Alias for backward compatibility
extract_component_code = extract_python_code


def extract_flow_json(text: str) -> dict | None:
    """Extract flow JSON from a ```flow_json code block in the response.

    The BuildFlowFromSpec tool instructs the agent to include the built
    flow data in a ```flow_json block so the assistant service can detect
    it and send a flow_preview event to the frontend.
    """
    match = re.search(FLOW_JSON_BLOCK_PATTERN, text, re.IGNORECASE)
    if not match:
        return None
    raw = match.group(1).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("Found ```flow_json``` block but JSON parsing failed: %s", e)
        return None
