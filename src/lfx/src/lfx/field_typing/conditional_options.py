"""Declarative dropdown choices shared by template refresh and flow configuration."""

from typing import Any

from pydantic import BaseModel


class ConditionalOptions(BaseModel):
    """Use these options when all named fields match; the first matching rule wins."""

    when: dict[str, str]
    options: list[str]


def resolve_conditional_options(field: dict[str, Any], values: dict[str, Any]) -> list[Any] | None:
    """Resolve choices from candidate values without executing component code."""
    for raw_rule in field.get("conditional_options") or []:
        rule = ConditionalOptions.model_validate(raw_rule)
        if all(values.get(name) == expected for name, expected in rule.when.items()):
            return rule.options
    return field.get("options")
