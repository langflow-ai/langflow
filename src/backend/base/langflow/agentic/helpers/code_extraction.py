"""Python code extraction from markdown responses."""

import re

PYTHON_CODE_BLOCK_PATTERN = r"```python\s*([\s\S]*?)```"
GENERIC_CODE_BLOCK_PATTERN = r"```\s*([\s\S]*?)```"
UNCLOSED_PYTHON_BLOCK_PATTERN = r"```python\s*([\s\S]*)$"
UNCLOSED_GENERIC_BLOCK_PATTERN = r"```\s*([\s\S]*)$"


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
