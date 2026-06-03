from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any

from lfx.base.mcp.util import create_input_schema_from_json_schema

if TYPE_CHECKING:
    from collections.abc import Callable


def _infer_schema_type(schema: dict[str, Any]) -> str | list[str]:
    """Infer a safe JSON schema type when one is missing.

    When inferring from anyOf/oneOf variants that include a null variant (e.g.,
    anyOf: [{type: string}, {type: null}]), returns ["<type>", "null"] to preserve
    nullability. Adding only the concrete type at the same schema level would cause
    JSON Schema's type constraint to intersect with the union, effectively coercing
    a formerly-nullable field into a non-nullable one.
    """
    if "properties" in schema or "additionalProperties" in schema:
        return "object"
    if "items" in schema:
        return "array"

    for union_key in ("anyOf", "oneOf"):
        variants = schema.get(union_key)
        if isinstance(variants, list):
            concrete_types: list[str] = []
            has_null_variant = False
            for variant in variants:
                if not isinstance(variant, dict):
                    continue
                variant_type = variant.get("type")
                if isinstance(variant_type, str):
                    if variant_type == "null":
                        has_null_variant = True
                    elif variant_type not in concrete_types:
                        concrete_types.append(variant_type)
                elif isinstance(variant_type, list):
                    for t in variant_type:
                        if isinstance(t, str):
                            if t == "null":
                                has_null_variant = True
                            elif t not in concrete_types:
                                concrete_types.append(t)
                else:
                    # No explicit type — infer from the variant's structure so that,
                    # e.g., enum-only variants like {"enum": ["a","b"]} are not
                    # silently treated as missing a concrete type.
                    inferred = _infer_schema_type(variant)
                    for t in [inferred] if isinstance(inferred, str) else inferred:
                        if t == "null":
                            has_null_variant = True
                        elif t not in concrete_types:
                            concrete_types.append(t)
            if concrete_types:
                result: list[str] = concrete_types + (["null"] if has_null_variant else [])
                return result[0] if len(result) == 1 else result

    # allOf represents composition/intersection rather than a union, but a
    # missing top-level type is still common. Infer a conservative type from
    # the composed variants, preferring object when any variant is object-like.
    # For allOf (intersection), "null" is only valid if every variant allows it,
    # so we track null separately and only include it when all variants are nullable.
    all_of_variants = schema.get("allOf")
    if isinstance(all_of_variants, list):
        concrete_types: list[str] = []
        variant_null_flags: list[bool] = []
        for variant in all_of_variants:
            if not isinstance(variant, dict):
                continue

            variant_types: list[str] = []
            variant_type = variant.get("type")
            if isinstance(variant_type, str):
                variant_types = [variant_type]
            elif isinstance(variant_type, list):
                variant_types = [t for t in variant_type if isinstance(t, str)]
            else:
                inferred = _infer_schema_type(variant)
                variant_types = [inferred] if isinstance(inferred, str) else [t for t in inferred if isinstance(t, str)]

            variant_null_flags.append("null" in variant_types)
            for t in variant_types:
                if t != "null" and t not in concrete_types:
                    concrete_types.append(t)

        # Only include "null" when every variant allows it (intersection semantics)
        all_nullable = bool(variant_null_flags) and all(variant_null_flags)
        if "object" in concrete_types:
            result = ["object"] + (["null"] if all_nullable else [])
            return result[0] if len(result) == 1 else result
        if len(concrete_types) == 1:
            result = concrete_types + (["null"] if all_nullable else [])
            return result[0] if len(result) == 1 else result

    enum_values = schema.get("enum")
    if isinstance(enum_values, list) and enum_values:
        # Inspect every enum value so mixed-type enums (e.g. [1, 1.5] or
        # ["a", 1] or [{"k": 1}, [1, 2]]) produce correct, complete type
        # information rather than
        # being truncated to the type of the first element.
        raw_types: set[str] = set()
        has_int = False
        has_float = False
        for v in enum_values:
            if v is None:
                raw_types.add("null")
            elif isinstance(v, bool):
                # bool must be checked before int (bool is a subclass of int)
                raw_types.add("boolean")
            elif isinstance(v, int):
                has_int = True
                raw_types.add("integer")
            elif isinstance(v, float):
                has_float = True
                raw_types.add("number")
            elif isinstance(v, str):
                raw_types.add("string")
            elif isinstance(v, dict):
                raw_types.add("object")
            elif isinstance(v, list):
                raw_types.add("array")
        # Promote integer → number when floats are also present, since every
        # JSON integer is a valid number but not vice-versa.
        if has_int and has_float:
            raw_types.discard("integer")
            raw_types.add("number")
        if raw_types:
            # Place "null" last to match the convention used for nullable unions.
            null_present = "null" in raw_types
            non_null = sorted(t for t in raw_types if t != "null")
            type_list = non_null + (["null"] if null_present else [])
            return type_list[0] if len(type_list) == 1 else type_list

    # Default leaf schemas with no reliable structural or value hints to string
    # so sanitization produces a concrete scalar type for tool arguments.
    return "string"


def _is_object_type(type_value: Any) -> bool:
    """Return True when a JSON Schema 'type' value represents an object.

    Handles both the scalar string form (``"object"``) and the array form
    (e.g. ``["object", "null"]``) that this module may produce when
    preserving nullability.
    """
    if isinstance(type_value, str):
        return type_value == "object"
    if isinstance(type_value, list):
        return "object" in type_value
    return False


def _needs_schema_sanitization(schema: dict[str, Any]) -> bool:
    """Check if a JSON schema needs sanitization (read-only traversal)."""
    if "type" not in schema or schema["type"] is None:
        return True

    if _is_object_type(schema.get("type")) and "properties" in schema and schema["properties"] is None:
        return True

    properties = schema.get("properties")
    if isinstance(properties, dict):
        for prop_schema in properties.values():
            if isinstance(prop_schema, dict) and _needs_schema_sanitization(prop_schema):
                return True

    items = schema.get("items")
    if isinstance(items, dict) and _needs_schema_sanitization(items):
        return True

    for union_key in ("anyOf", "oneOf", "allOf"):
        variants = schema.get(union_key)
        if isinstance(variants, list):
            for variant in variants:
                if isinstance(variant, dict) and _needs_schema_sanitization(variant):
                    return True

    return False


def _sanitize_schema_in_place(schema: dict[str, Any]) -> bool:
    """Recursively sanitize a JSON schema by filling missing type declarations."""
    changed = False

    if "type" not in schema or schema["type"] is None:
        schema["type"] = _infer_schema_type(schema)
        changed = True

    properties = schema.get("properties")
    if _is_object_type(schema.get("type")) and "properties" in schema and properties is None:
        schema["properties"] = {}
        changed = True

    if isinstance(properties, dict):
        for prop_schema in properties.values():
            if isinstance(prop_schema, dict) and _sanitize_schema_in_place(prop_schema):
                changed = True

    items = schema.get("items")
    if isinstance(items, dict) and _sanitize_schema_in_place(items):
        changed = True

    for union_key in ("anyOf", "oneOf", "allOf"):
        variants = schema.get(union_key)
        if isinstance(variants, list):
            for variant in variants:
                if isinstance(variant, dict) and _sanitize_schema_in_place(variant):
                    changed = True

    return changed


def sanitize_tool_args_schema_safe(tool: Any, log_fn: Callable[[str], None]) -> bool:
    """Call sanitize_tool_args_schema, logging any exception via log_fn instead of raising.

    Provider code (e.g. ``args_schema.model_json_schema()``) can raise a wide
    range of exception types beyond the three originally anticipated.  Catching
    only ``TypeError``/``ValueError``/``AttributeError`` meant that any other
    exception would propagate and crash tool loading.  This function catches
    all ``Exception`` subclasses so that sanitization failures are always
    isolated from the calling path.

    Args:
        tool: The tool object to sanitize.
        log_fn: Callable to log failure messages.

    Returns:
        True if sanitization succeeded, False if an exception occurred and was logged.
    """
    try:
        sanitize_tool_args_schema(tool)
    except Exception as e:  # noqa: BLE001 — intentional broad catch for provider isolation
        error_msg = str(e)[:200]  # Cap at 200 chars to avoid log spam from large errors
        log_fn(
            f"Skipping args schema sanitization for tool: {getattr(tool, 'name', 'unknown')} "
            f"due to {type(e).__name__}: {error_msg}"
        )
        return False
    else:
        return True


def sanitize_tool_args_schema(tool: Any) -> bool:
    """Normalize tool args schema to avoid missing-'type' failures in tool-calling stacks."""
    changed = False

    tool_args = getattr(tool, "args", None)
    if isinstance(tool_args, dict):
        for arg_schema in tool_args.values():
            if isinstance(arg_schema, dict) and _sanitize_schema_in_place(arg_schema):
                changed = True

    args_schema = getattr(tool, "args_schema", None)
    if args_schema is None or not hasattr(args_schema, "model_json_schema"):
        return changed

    raw_schema = args_schema.model_json_schema()
    if not isinstance(raw_schema, dict):
        return changed

    if not _needs_schema_sanitization(raw_schema):
        return changed

    schema_copy = deepcopy(raw_schema)
    schema_changed = _sanitize_schema_in_place(schema_copy)
    if schema_changed:
        tool.args_schema = create_input_schema_from_json_schema(schema_copy)
        changed = True
    return changed


def sanitize_tools_with_fallback(
    tools: list[Any],
    log_fn: Callable[[str], None],
    max_summary_examples: int = 10,
) -> tuple[list[Any], str | None]:
    """Sanitize a list of tools and return sanitized tools with excluded summary.

    Args:
        tools: List of tools to sanitize.
        log_fn: Callable to log individual failure messages (called for each failure).
        max_summary_examples: Maximum number of failed tool names to include in summary.

    Returns:
        Tuple of (sanitized_tools list, excluded_summary string or None if no failures).
        `excluded_summary` is a human-readable summary such as
         "tool1, tool2, and 5 more" or, when no example tool names are included
         (for example, if `max_summary_examples=0`), "and 5 more".
    """
    sanitized_tools = []
    failure_examples = []
    failure_count = 0

    for tool in tools:
        if sanitize_tool_args_schema_safe(tool, log_fn):
            sanitized_tools.append(tool)
        else:
            failure_count += 1
            if len(failure_examples) < max_summary_examples:
                failure_examples.append(getattr(tool, "name", "unknown"))

    if failure_count == 0:
        return sanitized_tools, None

    failure_summary = ", ".join(failure_examples)
    if failure_count > max_summary_examples:
        remaining = failure_count - max_summary_examples
        failure_summary = f"{failure_summary}, and {remaining} more" if failure_examples else f"and {remaining} more"

    return sanitized_tools, failure_summary
