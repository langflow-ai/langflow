"""Redact resolved global-variable values from component outputs.

When a component field is bound to a global variable (``load_from_db=True``), the
variable's stored value is fetched at run time and substituted into the component
parameters before execution. Many components echo those parameter values back in
their output or logs (e.g. a Text Input's output *is* its ``input_value``), which
leaks the resolved value in the UI's Component Output panel.

This module provides a single utility, :func:`redact_values`, that walks an
arbitrary object graph (dicts, lists, tuples, sets, strings, pydantic models,
and objects exposing ``model_dump``/``dict``) and replaces every occurrence of
each sensitive string with a placeholder of the form ``[REDACTED: <name>]``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

REDACTED_PLACEHOLDER_TEMPLATE = "[REDACTED: {name}]"
# Resolved values shorter than this are skipped to avoid mangling unrelated
# output. Generic globals like a Split Text separator (``,``) or a single-line
# delimiter (``\n``) would otherwise rewrite every matching character in the
# results/logs/artifacts payloads. Four characters is the smallest length that
# keeps real configuration values redactable (model names like ``gpt-4`` are
# 5+) while skipping the high-false-positive single/two/three-char cases.
_MIN_REDACTABLE_LENGTH = 4


def _placeholder_for(variable_name: str | None) -> str:
    return REDACTED_PLACEHOLDER_TEMPLATE.format(name=variable_name or "global variable")


def _redact_string(value: str, redaction_map: Mapping[str, str]) -> str:
    """Replace every occurrence of each sensitive value in ``value``.

    Strings are replaced by literal substring match. The map is applied in
    descending length order so a longer secret that contains a shorter one is
    redacted before the shorter match can partially redact it.
    """
    if not value:
        return value
    redacted = value
    for secret in sorted(redaction_map, key=len, reverse=True):
        if not secret or len(secret) < _MIN_REDACTABLE_LENGTH:
            continue
        if secret in redacted:
            redacted = redacted.replace(secret, redaction_map[secret])
    return redacted


def _model_dump(obj: Any) -> dict | None:
    """Best-effort conversion of a model-like object to a plain dict."""
    model_dump = getattr(obj, "model_dump", None)
    if callable(model_dump):
        try:
            return model_dump()
        except Exception:  # noqa: BLE001
            return None
    to_dict = getattr(obj, "dict", None)
    if callable(to_dict):
        try:
            return to_dict()
        except Exception:  # noqa: BLE001
            return None
    return None


def redact_values(obj: Any, redaction_map: Mapping[str, str]) -> Any:
    """Return a deep copy of ``obj`` with sensitive substrings replaced.

    ``redaction_map`` maps a literal sensitive value to its replacement string.

    The traversal is non-mutating: new containers are always returned so the
    caller's original structures (e.g. component ``results`` still held in
    memory for downstream vertices) are left untouched.
    """
    if not redaction_map or obj is None:
        return obj

    if isinstance(obj, str):
        return _redact_string(obj, redaction_map)

    if isinstance(obj, Mapping):
        return {key: redact_values(value, redaction_map) for key, value in obj.items()}

    # Strings are Sequence-like; handle them before generic sequences above.
    if isinstance(obj, (list, tuple, set, frozenset)):
        redacted_items = [redact_values(item, redaction_map) for item in obj]
        if isinstance(obj, tuple):
            return tuple(redacted_items)
        if isinstance(obj, set):
            return set(redacted_items)
        if isinstance(obj, frozenset):
            return frozenset(redacted_items)
        return redacted_items

    if isinstance(obj, (bytes, bytearray, memoryview, int, float, bool)):
        return obj

    # Pydantic / dataclass-ish objects: dump, redact, return plain dict.
    dumped = _model_dump(obj)
    if dumped is not None:
        return {key: redact_values(value, redaction_map) for key, value in dumped.items()}

    # Fall back to a generic iteration-guarded path for other Sequence-like
    # objects (e.g. pandas Series). We only recurse when we can round-trip via
    # str() to avoid dropping opaque values entirely.
    if isinstance(obj, Sequence):
        return [redact_values(item, redaction_map) for item in obj]

    return obj


def build_redaction_map(resolved_values: Mapping[str, str]) -> dict[str, str]:
    """Build a ``{sensitive_value: placeholder}`` mapping.

    ``resolved_values`` maps a resolved value (the secret) to the originating
    global variable name (e.g. ``{"sk-abc...": "OPENAI_API_KEY"}``). Empty
    values and values shorter than :data:`_MIN_REDACTABLE_LENGTH` characters
    are skipped because redacting them would produce noisy, wide-reaching
    replacements across unrelated output text.
    """
    redaction_map: dict[str, str] = {}
    for value, name in resolved_values.items():
        if not isinstance(value, str) or len(value) < _MIN_REDACTABLE_LENGTH:
            continue
        redaction_map[value] = _placeholder_for(name)
    return redaction_map
