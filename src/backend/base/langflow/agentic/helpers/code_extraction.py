"""Code and data extraction from markdown responses."""

import ast
import json
import logging
import re

logger = logging.getLogger(__name__)

FLOW_JSON_BLOCK_PATTERN = r"```flow_json\s*([\s\S]*?)```"
ANY_CODE_BLOCK_PATTERN = r"```[\s\S]*?```|```[\s\S]*$"
_OPENING_FENCE_RE = re.compile(r"^\s*```\s*([A-Za-z0-9_-]+)?\s*$")
_CLOSING_FENCE_RE = re.compile(r"^\s*```\s*$")
_COMPONENT_CLASS_RE = re.compile(r"^\s*class\s+\w+\s*\((?P<bases>[^)]*)\)", re.MULTILINE)


def extract_python_code(text: str) -> str | None:
    """Extract Python code from markdown code blocks.

    Handles both closed (```python ... ```) and unclosed blocks.
    Returns the first code block that appears to be a Langflow component.
    """
    matches = _find_code_blocks(text)
    if not matches:
        return None

    component_code = _find_component_code(matches)
    if component_code:
        return component_code

    first_block = matches[0].strip()
    return first_block or None


def _find_code_blocks(text: str) -> list[str]:
    """Find all code blocks in text, handling both closed and unclosed blocks."""
    python_blocks, generic_blocks, unclosed_blocks = _parse_code_fences(text)
    return python_blocks or generic_blocks or unclosed_blocks


def _parse_code_fences(text: str) -> tuple[list[str], list[str], list[str]]:
    """Parse markdown fences, treating only a standalone ``` line as a closing fence."""
    python_blocks: list[str] = []
    generic_blocks: list[str] = []
    unclosed_blocks: list[str] = []
    current_language: str | None = None
    current_lines: list[str] = []

    for line in text.splitlines(keepends=True):
        if current_language is None:
            match = _OPENING_FENCE_RE.match(line)
            if not match:
                continue
            language = (match.group(1) or "").lower()
            if language in {"", "python"}:
                current_language = language or "generic"
                current_lines = []
            continue

        if _CLOSING_FENCE_RE.match(line):
            block = "".join(current_lines).strip()
            if block:
                if current_language == "python":
                    python_blocks.append(block)
                elif current_language == "generic":
                    generic_blocks.append(block)
            current_language = None
            current_lines = []
            continue

        current_lines.append(line)

    if current_language in {"python", "generic"}:
        block = "".join(current_lines).strip()
        if block:
            unclosed_blocks.append(block)

    return python_blocks, generic_blocks, unclosed_blocks


def _find_unclosed_code_block(text: str) -> list[str]:
    """Handle LLM responses that don't close the code block with ```."""
    _python_blocks, _generic_blocks, unclosed_blocks = _parse_code_fences(text)
    return unclosed_blocks


def _find_component_code(matches: list[str]) -> str | None:
    """Find the first match that looks like a Langflow component."""
    for match in matches:
        code = match.strip()
        if code and _contains_component_class(code):
            return code
    return None


def _contains_component_class(code: str) -> bool:
    """Return True when code defines a class inheriting from Component."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return _contains_component_class_header(code)

    return any(
        isinstance(node, ast.ClassDef) and any(_is_component_base(base) for base in node.bases)
        for node in ast.walk(tree)
    )


def _is_component_base(base: ast.expr) -> bool:
    if isinstance(base, ast.Name):
        return base.id == "Component"
    if isinstance(base, ast.Attribute):
        return base.attr == "Component"
    if isinstance(base, ast.Subscript):
        return _is_component_base(base.value)
    return False


def _contains_component_class_header(code: str) -> bool:
    for match in _COMPONENT_CLASS_RE.finditer(code):
        bases = [base.strip() for base in match.group("bases").split(",")]
        if any(base == "Component" or base.endswith(".Component") for base in bases):
            return True
    return False


def extract_component_code(text: str) -> str | None:
    """Extract the first code block that defines a Langflow component."""
    return _find_component_code(_find_code_blocks(text))


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
