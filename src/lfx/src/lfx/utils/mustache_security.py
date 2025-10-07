"""Security utilities for mustache template processing."""

import re
from typing import Any

# Regex pattern for simple variables only - same as frontend
SIMPLE_VARIABLE_PATTERN = re.compile(r"\{\{([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\}\}")

# Patterns for complex mustache syntax that we want to block
DANGEROUS_PATTERNS = [
    re.compile(r"\{\{#"),  # Conditionals/sections start
    re.compile(r"\{\{/"),  # Conditionals/sections end
    re.compile(r"\{\{\^"),  # Inverted sections
    re.compile(r"\{\{&"),  # Unescaped variables
    re.compile(r"\{\{>"),  # Partials
    re.compile(r"\{\{!"),  # Comments
    re.compile(r"\{\{\."),  # Current context
]


def validate_mustache_template(template: str) -> None:
    """Validate that a mustache template only contains simple variable substitutions.

    Raises ValueError if complex mustache syntax is detected.
    """
    if not template:
        return

    # Check for dangerous patterns
    for pattern in DANGEROUS_PATTERNS:
        if pattern.search(template):
            msg = (
                "Complex mustache syntax is not allowed. Only simple variable substitution "
                "like {{variable}} or {{object.property}} is permitted."
            )
            raise ValueError(msg)

    # Check that all {{ }} patterns are simple variables
    all_mustache_patterns = re.findall(r"\{\{[^}]*\}\}", template)
    for pattern in all_mustache_patterns:
        if not SIMPLE_VARIABLE_PATTERN.match(pattern):
            msg = (
                f"Invalid mustache variable: {pattern}. Only simple variable names "
                "like {{variable}} or {{object.property}} are allowed."
            )
            raise ValueError(msg)


def safe_mustache_render(template: str, variables: dict[str, Any]) -> str:
    """Safely render a mustache template with only simple variable substitution.

    Args:
        template: The mustache template string
        variables: Dictionary of variables to substitute

    Returns:
        The rendered template

    Raises:
        ValueError: If template contains complex mustache syntax
    """
    # Validate template first
    validate_mustache_template(template)

    # Simple replacement - find all simple variables and replace them
    def replace_variable(match):
        var_path = match.group(1)

        # Handle dot notation (e.g., user.name)
        parts = var_path.split(".")
        value = variables

        try:
            for part in parts:
                value = value.get(part, "") if isinstance(value, dict) else getattr(value, part, "")

            # Convert to string
            return str(value) if value is not None else ""
        except (KeyError, AttributeError):
            # Variable not found - return empty string like mustache does
            return ""

    # Replace all simple variables
    return SIMPLE_VARIABLE_PATTERN.sub(replace_variable, template)
