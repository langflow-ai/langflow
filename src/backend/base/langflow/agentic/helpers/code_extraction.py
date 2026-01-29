"""Python code extraction from markdown responses."""

import re

PYTHON_CODE_BLOCK_PATTERN = r"```python\s*([\s\S]*?)```"
GENERIC_CODE_BLOCK_PATTERN = r"```\s*([\s\S]*?)```"
UNCLOSED_PYTHON_BLOCK_PATTERN = r"```python\s*([\s\S]*)$"
UNCLOSED_GENERIC_BLOCK_PATTERN = r"```\s*([\s\S]*)$"
ANY_CODE_BLOCK_PATTERN = r"```[\s\S]*?```|```[\s\S]*$"


def extract_component_code(text: str) -> str | None:
    """Extract component code if the response contains a valid Langflow component.

    A valid component must:
    - Have a class that inherits from Component (or similar base classes)
    - Have inputs and/or outputs defined

    Returns the code if it looks like a complete component, None otherwise.
    """
    matches = _find_code_blocks(text)
    if not matches:
        return None

    component_code = _find_component_code(matches)
    if not component_code:
        return None

    # Verify it's a complete component (has inputs or outputs defined)
    if not _is_complete_component(component_code):
        return None

    return component_code


def _is_complete_component(code: str) -> bool:
    """Check if code is a complete Langflow component with inputs/outputs."""
    # Must have a class inheriting from Component or similar
    component_pattern = r"class\s+\w+\s*\([^)]*(?:Component|CustomComponent|LCToolComponent)[^)]*\)"
    if not re.search(component_pattern, code):
        return False

    # Must have inputs or outputs defined
    has_inputs = "inputs" in code and ("[" in code or "Input" in code)
    has_outputs = "outputs" in code and ("[" in code or "Output" in code)

    return has_inputs or has_outputs


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
