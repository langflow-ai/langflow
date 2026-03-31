"""Sensitive field redaction for component templates.

Provides `is_sensitive_field` for checking field names, and
`redact_template`/`redact_node` utilities for bulk redaction.
"""

from __future__ import annotations

SENSITIVE_KEYWORDS = {"api_key", "password", "secret", "token", "access_key", "private_key"}


def is_sensitive_field(field_name: str) -> bool:
    """Check if a field name looks like it holds sensitive data."""
    name_lower = field_name.lower()
    return any(kw in name_lower for kw in SENSITIVE_KEYWORDS)


def redact_template(template: dict) -> dict:
    """Return a copy of the template with sensitive field values masked."""
    redacted = {}
    for key, value in template.items():
        if isinstance(value, dict):
            if is_sensitive_field(key) and "value" in value and value["value"]:
                redacted[key] = {**value, "value": "***REDACTED***"}
            else:
                redacted[key] = {**value}
        else:
            redacted[key] = value
    return redacted


def redact_node(node_data: dict) -> dict:
    """Redact sensitive fields in a node's template."""
    result = {**node_data}
    if "node" in result and "template" in result["node"]:
        result = {**result, "node": {**result["node"]}}
        result["node"]["template"] = redact_template(result["node"]["template"])
    return result
