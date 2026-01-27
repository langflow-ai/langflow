"""Security utilities for mustache template processing."""

import re
from typing import Any

# Regex pattern for simple variables only - same as frontend
SIMPLE_VARIABLE_PATTERN = re.compile(r"\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}")

# Regex pattern for global variable references (prefixed with @)
# e.g., {{@my_global_var}}
GLOBAL_VARIABLE_PATTERN = re.compile(r"\{\{@([a-zA-Z_][a-zA-Z0-9_]*)\}\}")

# Combined pattern that matches either simple variables or global variable references
COMBINED_VARIABLE_PATTERN = re.compile(r"\{\{(@)?([a-zA-Z_][a-zA-Z0-9_]*)\}\}")

# Patterns for complex mustache syntax that we want to block
DANGEROUS_PATTERNS = [
    re.compile(r"\{\{\{"),  # Triple braces (unescaped HTML in Mustache)
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

    Supports both regular variables ({{variable}}) and global variable references ({{@variable}}).

    Raises ValueError if complex mustache syntax is detected.
    """
    if not template:
        return

    # Check for dangerous patterns
    for pattern in DANGEROUS_PATTERNS:
        if pattern.search(template):
            msg = (
                "Complex mustache syntax is not allowed. Only simple variable substitution "
                "like {{variable}} or global variable references like {{@variable}} are permitted."
            )
            raise ValueError(msg)

    # Check that all {{ }} patterns are either simple variables or global variable references
    all_mustache_patterns = re.findall(r"\{\{[^}]*\}\}", template)
    for pattern in all_mustache_patterns:
        # Check if it matches either simple variable or global variable pattern
        if not SIMPLE_VARIABLE_PATTERN.match(pattern) and not GLOBAL_VARIABLE_PATTERN.match(pattern):
            msg = (
                f"Invalid mustache variable: {pattern}. Only simple variable names like {{{{variable}}}} "
                "or global variable references like {{{{@variable}}}} are allowed."
            )
            raise ValueError(msg)


def extract_global_variable_names(template: str) -> list[str]:
    """Extract names of global variables referenced in a template.

    Args:
        template: The mustache template string

    Returns:
        List of global variable names (without the @ prefix)
    """
    if not template:
        return []
    return GLOBAL_VARIABLE_PATTERN.findall(template)


def safe_mustache_render(
    template: str,
    variables: dict[str, Any],
    global_variables: dict[str, Any] | None = None,
) -> str:
    """Safely render a mustache template with variable substitution.

    This function performs a single-pass replacement of all {{variable}} and {{@variable}} patterns.
    Variable values that themselves contain mustache-like patterns (e.g., "{{other}}")
    will NOT be processed - they are treated as literal strings. This prevents
    injection attacks where user-controlled values could introduce new template variables.

    Args:
        template: The mustache template string
        variables: Dictionary of regular variables to substitute (for {{variable}})
        global_variables: Dictionary of global variables to substitute (for {{@variable}})

    Returns:
        The rendered template

    Raises:
        ValueError: If template contains complex mustache syntax
    """
    # Validate template first
    validate_mustache_template(template)

    if global_variables is None:
        global_variables = {}

    # Combined replacement - handle both regular and global variables
    def replace_variable(match):
        is_global = match.group(1) == "@"
        var_name = match.group(2)

        if is_global:
            # Get from global variables
            value = global_variables.get(var_name, "")
        else:
            # Get from regular variables
            value = variables.get(var_name, "")

        # Convert to string
        return str(value) if value is not None else ""

    # Replace all variables (both regular and global) in a single pass
    return COMBINED_VARIABLE_PATTERN.sub(replace_variable, template)
