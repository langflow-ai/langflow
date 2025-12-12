"""JSON Schema utilities for LFX."""

from typing import Any, Union

from pydantic import AliasChoices, BaseModel, Field, create_model

from lfx.log.logger import logger

NULLABLE_TYPE_LENGTH = 2  # Number of types in a nullable union (the type itself + null)
MAX_ANYOF_ITEMS = 2
MAX_OBJECT_PROPERTIES_IN_ANYOF = 3
MAX_OBJECT_PROPERTIES = 5


def _snake_to_camel(name: str) -> str:
    """Convert snake_case to camelCase, preserving leading/trailing underscores."""
    if not name:
        return name

    # Handle leading underscores
    leading = ""
    start_idx = 0
    while start_idx < len(name) and name[start_idx] == "_":
        leading += "_"
        start_idx += 1

    # Handle trailing underscores
    trailing = ""
    end_idx = len(name)
    while end_idx > start_idx and name[end_idx - 1] == "_":
        trailing += "_"
        end_idx -= 1

    # Convert the middle part
    middle = name[start_idx:end_idx]
    if not middle:
        return name  # All underscores

    components = middle.split("_")
    camel = components[0] + "".join(word.capitalize() for word in components[1:])

    return leading + camel + trailing


def create_input_schema_from_json_schema(schema: dict[str, Any]) -> type[BaseModel]:
    """Dynamically build a Pydantic model from a JSON schema (with $defs).

    Non-required fields become Optional[...] with default=None.
    """
    if schema.get("type") != "object":
        msg = "Root schema must be type 'object'"
        raise ValueError(msg)

    defs: dict[str, dict[str, Any]] = schema.get("$defs", {})
    model_cache: dict[str, type[BaseModel]] = {}

    def resolve_ref(s: dict[str, Any] | None) -> dict[str, Any]:
        """Follow a $ref chain until you land on a real subschema."""
        if s is None:
            return {}
        while "$ref" in s:
            ref_name = s["$ref"].split("/")[-1]
            s = defs.get(ref_name)
            if s is None:
                logger.warning(f"Parsing input schema: Definition '{ref_name}' not found")
                return {"type": "string"}
        return s

    def is_complex_schema(schema: dict[str, Any]) -> bool:
        """Check if a schema is too complex for UI rendering."""
        # Check for additionalProperties with complex anyOf structures
        if "additionalProperties" in schema:
            additional_props = schema["additionalProperties"]
            if isinstance(additional_props, dict) and "anyOf" in additional_props:
                anyof_items = additional_props["anyOf"]
                # If anyOf has many items or contains complex objects
                if len(anyof_items) > MAX_ANYOF_ITEMS:
                    return True
                for item in anyof_items:
                    if isinstance(item, dict) and item.get("type") == "object":
                        if "properties" in item and len(item["properties"]) > MAX_OBJECT_PROPERTIES_IN_ANYOF:
                            return True
                        if "additionalProperties" in item:
                            return True
            elif isinstance(additional_props, dict) and additional_props.get("type") == "object":
                return True

        # Check for complex object with many properties
        if schema.get("type") == "object" and "properties" in schema:
            properties_count = len(schema["properties"])
            if properties_count > MAX_OBJECT_PROPERTIES:  # Threshold for complexity
                return True

        return False

    def parse_type(s: dict[str, Any] | None) -> Any:
        """Map a JSON Schema subschema to a Python type (possibly nested)."""
        if s is None:
            return None
        s = resolve_ref(s)

        # Handle boolean values in additionalProperties
        if "additionalProperties" in s and isinstance(s["additionalProperties"], bool) and s["additionalProperties"]:
            return dict[str, Any]
            # If false, it means no additional properties are allowed.
            # We can represent this by returning a type that won't be iterable.
            # However, for the purpose of building a model, we can perhaps return an empty dict
            # or handle it in the _build_model function.
            # For now, let's see if just handling `True` is enough.

        # Handle objects with additionalProperties (dynamic fields) but no explicit properties
        # This is common for dictionaries/maps where keys are dynamic
        if s.get("type") == "object" and "additionalProperties" in s and not s.get("properties"):
            # For dynamic dictionaries, returning Dict[str, Any] allows Langflow UI to potentially
            # render a JSON editor or Key-Value input.
            # Complex recursive types (like Unions) inside a Dict often cause UI rendering issues.
            return dict[str, Any]

        if "anyOf" in s:
            # Handle common pattern for nullable types (anyOf with string and null)
            subtypes = [sub.get("type") for sub in s["anyOf"] if isinstance(sub, dict) and "type" in sub]

            # Check if this is a simple nullable type (e.g., str | None)
            if len(subtypes) == NULLABLE_TYPE_LENGTH and "null" in subtypes:
                # Get the non-null type
                non_null_type = next(t for t in subtypes if t != "null")
                # Map it to Python type
                if isinstance(non_null_type, str):
                    return {
                        "string": str,
                        "integer": int,
                        "number": float,
                        "boolean": bool,
                        "object": dict,
                        "array": list,
                    }.get(non_null_type, Any)
                return Any

            # For other anyOf cases, return a Union of all possible types
            # This ensures Pydantic generates a schema with oneOf/anyOf, allowing the UI to render appropriate inputs
            try:
                subtypes = []
                for sub in s["anyOf"]:
                    parsed = parse_type(sub)
                    if parsed is not None and parsed is not type(None):
                        subtypes.append(parsed)

                # Remove duplicates while preserving order
                unique_types = []
                for t in subtypes:
                    if t not in unique_types:
                        unique_types.append(t)

                if not unique_types:
                    return Any

                if len(unique_types) == 1:
                    return unique_types[0]

                # Safe Union creation for dynamic types
                # Using __getitem__ with a tuple is the standard way to create Union[A, B] dynamically
                # But we wrap in try-except to fallback to Any if type construction fails
                return Union[tuple(unique_types)]  # noqa: UP007
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Failed to create Union type from anyOf: {e}")
                return Any

        t = s.get("type", "any")  # Use string "any" as default instead of Any type

        # Handle case where type is a list (e.g. ["string", "null"])
        if isinstance(t, list):
            # Convert to anyOf format and recurse
            return parse_type({"anyOf": [{"type": sub_t} for sub_t in t]})

        if t == "array":
            item_schema = s.get("items", {})
            if item_schema:
                # Check for complex structures that UI cannot handle properly
                is_complex = False

                # Check if items schema has additionalProperties with anyOf (very complex)
                if "additionalProperties" in item_schema:
                    additional_props = item_schema["additionalProperties"]
                    if isinstance(additional_props, dict) and "anyOf" in additional_props:
                        anyof_items = additional_props.get("anyOf", [])
                        # If anyOf has more than 2 items or contains complex nested structures
                        if len(anyof_items) > MAX_ANYOF_ITEMS:
                            is_complex = True
                        else:
                            # Check if anyOf items are complex objects themselves
                            for item in anyof_items:
                                if isinstance(item, dict) and item.get("type") == "object":
                                    is_complex = True
                                    break

                if not is_complex and item_schema.get("type") == "object" and "properties" in item_schema:
                    # Complex object with many properties
                    properties_count = len(item_schema.get("properties", {}))
                    if properties_count > MAX_OBJECT_PROPERTIES:  # Threshold for complexity
                        is_complex = True

                # For complex array items, fall back to list[dict[str, Any]] instead of str
                # This ensures the field appears as an array input in the UI
                if is_complex:
                    logger.debug("Detected complex array schema, using list[dict[str, Any]] for UI compatibility")
                    return str  # Keep as str to force JSON input in UI

                schema_type: Any = parse_type(item_schema)
                return list[schema_type]

        if t == "object":
            # Check if object schema is too complex for UI rendering
            if is_complex_schema(s):
                logger.debug("Detected complex object schema, falling back to str (JSON input) for UI compatibility")
                return str
            # inline object not in $defs ⇒ anonymous nested model
            return _build_model(f"AnonModel{len(model_cache)}", s)

        # primitive fallback
        return {
            "string": str,
            "integer": int,
            "number": float,
            "boolean": bool,
            "object": dict,
            "array": list,
        }.get(t, Any)

    def _build_model(name: str, subschema: dict[str, Any]) -> type[BaseModel]:
        """Create (or fetch) a BaseModel subclass for the given object schema."""
        # If this came via a named $ref, use that name
        if "$ref" in subschema:
            refname = subschema["$ref"].split("/")[-1]
            if refname in model_cache:
                return model_cache[refname]
            target = defs.get(refname)
            if not target:
                msg = f"Definition '{refname}' not found"
                raise ValueError(msg)
            cls = _build_model(refname, target)
            model_cache[refname] = cls
            return cls

        # Named anonymous or inline: avoid clashes by name
        if name in model_cache:
            return model_cache[name]

        props = subschema.get("properties", {})
        reqs = set(subschema.get("required", []))
        fields: dict[str, Any] = {}

        for prop_name, prop_schema in props.items():
            py_type = parse_type(prop_schema)
            is_required = prop_name in reqs
            if not is_required:
                py_type = py_type | None
                default = prop_schema.get("default", None)
            else:
                default = ...  # required by Pydantic

            # Add alias for camelCase if field name is snake_case
            field_kwargs = {"description": prop_schema.get("description")}
            if "_" in prop_name:
                camel_case_name = _snake_to_camel(prop_name)
                if camel_case_name != prop_name:  # Only add alias if it's different
                    field_kwargs["validation_alias"] = AliasChoices(prop_name, camel_case_name)

            fields[prop_name] = (py_type, Field(default, **field_kwargs))

        # Handle additionalProperties for objects without explicit properties
        if "additionalProperties" in subschema:
            additional_props = subschema["additionalProperties"]
            if isinstance(additional_props, bool):
                if additional_props:
                    # Allow any additional properties - but this is complex for UI
                    # Fall back to str (JSON input) instead
                    logger.debug(
                        f"Object '{name}' allows additional properties, using str (JSON input) for UI compatibility"
                    )
                    # Don't create fields, just return str type from parse_type
            elif isinstance(additional_props, dict) and not props:
                # Handle dict-based additionalProperties
                additional_props_schema = resolve_ref(additional_props)
                if is_complex_schema(additional_props_schema) or "anyOf" in additional_props_schema:
                    # Complex additional properties - use str (JSON input)
                    logger.debug(
                        f"Object '{name}' has complex additional properties, "
                        "using str (JSON input) for UI compatibility"
                    )
                    # Will be handled by falling back to str in caller
                else:
                    py_type = parse_type(additional_props_schema) or Any
                    fields["data"] = (dict[str, py_type], Field(default_factory=dict, description="Dynamic field data"))

        model_cls = create_model(name, **fields)
        model_cache[name] = model_cls
        return model_cls

    # build the top - level "InputSchema" from the root properties
    top_props = schema.get("properties", {})
    top_reqs = set(schema.get("required", []))
    top_fields: dict[str, Any] = {}

    for fname, fdef in top_props.items():
        py_type = parse_type(fdef)
        if fname not in top_reqs:
            py_type = py_type | None
            default = fdef.get("default", None)
        else:
            default = ...

        # Add alias for camelCase if field name is snake_case
        field_kwargs = {"description": fdef.get("description")}
        if "_" in fname:
            camel_case_name = _snake_to_camel(fname)
            if camel_case_name != fname:  # Only add alias if it's different
                field_kwargs["validation_alias"] = AliasChoices(fname, camel_case_name)

        top_fields[fname] = (py_type, Field(default, **field_kwargs))

    return create_model("InputSchema", **top_fields)
