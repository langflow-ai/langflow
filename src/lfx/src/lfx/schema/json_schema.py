"""JSON Schema utilities for LFX."""

from typing import Any

from pydantic import BaseModel, Field, create_model

from lfx.log.logger import logger

NULLABLE_TYPE_LENGTH = 2  # Number of types in a nullable union (the type itself + null)


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

    def parse_type(s: dict[str, Any] | None) -> Any:
        """Map a JSON Schema subschema to a Python type (possibly nested)."""
        if s is None:
            return None
        s = resolve_ref(s)

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

            # For other anyOf cases, use the first non-null type
            subtypes = [parse_type(sub) for sub in s["anyOf"]]
            non_null_types = [t for t in subtypes if t is not None and t is not type(None)]
            if non_null_types:
                return non_null_types[0]
            return str

        t = s.get("type", "any")  # Use string "any" as default instead of Any type
        if t == "array":
            item_schema = s.get("items", {})
            schema_type: Any = parse_type(item_schema)
            return list[schema_type]

        if t == "object":
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

            fields[prop_name] = (py_type, Field(default, description=prop_schema.get("description")))

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
        top_fields[fname] = (py_type, Field(default, description=fdef.get("description")))

    return create_model("InputSchema", **top_fields)
