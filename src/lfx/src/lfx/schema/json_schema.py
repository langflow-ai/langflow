"""JSON Schema utilities for LFX."""

from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, create_model

from lfx.log.logger import logger


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


def _safe_field_name(name: str, used: set[str], reserved: set[str] | None = None) -> str:
    """Return a Pydantic-safe field name for a JSON Schema property name.

    Pydantic reserves leading-underscore names for private attributes, so a
    property such as Glean's ``_user_goal`` (a legal JSON Schema name) makes
    ``create_model`` raise ``NameError``. Strip the leading underscores and
    de-duplicate deterministically; the original wire name is kept reachable
    through ``validation_alias``.

    ``reserved`` lists every wire property name of this object. When stripping
    the leading underscore would collide with another property's wire name
    (``_foo`` sanitized to ``foo`` while ``foo`` is also a real property), the
    candidate is shifted so the sanitized field name cannot capture input
    intended for the other property.
    """
    base = name.lstrip("_") or "field"
    candidate = base
    i = 1
    while candidate in used or (reserved is not None and candidate in reserved and candidate != name):
        candidate = f"{base}_{i}"
        i += 1
    used.add(candidate)
    return candidate


def _alias_choices(safe_name: str, wire_name: str, reserved_names: set[str]) -> AliasChoices:
    """Build validation aliases: safe field name first, then wire and camelCase.

    The safe name must stay first: it is the name the UI and the LLM-facing JSON
    schema use. It can never shadow a sibling property, because
    ``_safe_field_name`` already skips any candidate that is another property's
    wire name (``_foo`` next to ``foo`` becomes ``foo_1``).
    A camelCase alias is included only when it cannot shadow a sibling's wire
    name or sanitized field name.
    """
    aliases = [safe_name]
    if safe_name != wire_name:
        aliases.append(wire_name)
    if "_" in wire_name:
        camel_case_name = _snake_to_camel(wire_name)
        if camel_case_name not in reserved_names and camel_case_name not in aliases:
            aliases.append(camel_case_name)
    return AliasChoices(*aliases)


def create_input_schema_from_json_schema(schema: dict[str, Any]) -> type[BaseModel]:
    """Dynamically build a Pydantic model from a JSON schema (with $defs).

    Non-required fields become Optional[...] with default=None.
    """
    if schema.get("type") != "object":
        msg = "Root schema must be type 'object'"
        raise ValueError(msg)

    defs: dict[str, dict[str, Any]] = schema.get("$defs", {})
    model_cache: dict[str, type[BaseModel]] = {}
    # Tracks $def names currently being built to detect self-referential schemas
    building: set[str] = set()
    parsing_any_of: set[int] = set()
    # Monotonic counter for anonymous nested-object models. Using len(model_cache)
    # is unsafe during recursive descent because the cache is populated only after
    # a build completes, causing concurrent in-progress models to collide on the
    # same name and falsely trigger the self-reference guard.
    anon_counter: list[int] = [0]

    def _next_anon_name() -> str:
        n = anon_counter[0]
        anon_counter[0] += 1
        return f"AnonModel{n}"

    def resolve_ref(s: dict[str, Any] | None) -> dict[str, Any]:
        """Follow a $ref chain until you land on a real subschema."""
        if s is None:
            return {}
        visited: set[str] = set()
        while "$ref" in s:
            ref_name = s["$ref"].split("/")[-1]
            if ref_name in visited:
                logger.warning("Parsing input schema: Circular $ref detected for '%s', treating as string", ref_name)
                return {"type": "string"}
            visited.add(ref_name)
            s = defs.get(ref_name)
            if s is None:
                logger.warning("Parsing input schema: Definition '%s' not found", ref_name)
                return {"type": "string"}
        return s

    def parse_type(s: dict[str, Any] | None) -> Any:
        """Map a JSON Schema subschema to a Python type (possibly nested)."""
        if s is None:
            return None
        # Preserve the original subschema so we can detect when an object was
        # reached via a named $ref and route it through _build_model's $ref branch
        # for stable naming and cache reuse.
        original = s
        s = resolve_ref(s)

        if "anyOf" in s:
            schema_id = id(s)
            if schema_id in parsing_any_of:
                logger.warning("Parsing input schema: Recursive anyOf detected, treating recursive branch as Any")
                return Any
            parsing_any_of.add(schema_id)
            try:
                subtypes = [parse_type(sub) for sub in s["anyOf"]]
            finally:
                parsing_any_of.discard(schema_id)
            if not subtypes:
                return str
            union_type = subtypes[0]
            for subtype in subtypes[1:]:
                union_type |= subtype
            return union_type

        t = s.get("type", "any")  # Use string "any" as default instead of Any type
        if isinstance(t, list):
            # JSON Schema: "type": ["string", "null"] for nullable
            non_null = [x for x in t if x != "null" and isinstance(x, str)]
            if non_null:
                prim = {
                    "string": str,
                    "integer": int,
                    "number": float,
                    "boolean": bool,
                    "object": dict,
                    "array": list,
                }.get(non_null[0], Any)
                return prim | None if "null" in t else prim
            return Any
        if t == "array":
            item_schema = s.get("items", {})
            schema_type: Any = parse_type(item_schema)
            return list[schema_type]

        if t == "object":
            # Generic object (no properties) ⇒ dict[str, Any] for free-form key-value pairs
            # This preserves nested dictionaries (fixes issue #9881)
            if not s.get("properties"):
                return dict[str, Any]
            # If the object was reached via a named $ref, pass the original $ref-bearing
            # subschema so _build_model uses its $ref branch (stable name, cache reuse).
            if isinstance(original, dict) and "$ref" in original:
                return _build_model(_next_anon_name(), original)
            # Inline object with defined properties ⇒ anonymous nested model
            return _build_model(_next_anon_name(), s)

        # primitive fallback
        return {
            "null": type(None),
            "string": str,
            "integer": int,
            "number": float,
            "boolean": bool,
            "object": dict,
            "array": list,
        }.get(t, Any)

    def _build_model(name: str, subschema: dict[str, Any]) -> type[BaseModel]:
        """Create (or fetch) a BaseModel subclass for the given object schema."""
        # If this came via a named $ref, use that name. The recursive _build_model
        # call below handles `building` tracking and cache population itself, so we
        # must NOT pre-add `refname` to `building` here — doing so would cause the
        # recursive call to falsely see itself as self-referential and fall back to
        # dict on the very first visit of a non-recursive def.
        if "$ref" in subschema:
            refname = subschema["$ref"].split("/")[-1]
            if refname in model_cache:
                return model_cache[refname]
            # Already in progress (true self-reference encountered via $ref)
            if refname in building:
                logger.warning("Parsing input schema: Self-referential $ref '%s' detected, treating as dict", refname)
                return dict  # type: ignore[return-value]
            target = defs.get(refname)
            if not target:
                msg = f"Definition '{refname}' not found"
                raise ValueError(msg)
            return _build_model(refname, target)

        # Named anonymous or inline: avoid clashes by name
        if name in model_cache:
            return model_cache[name]
        # Self-referential: this model name is already being built — fall back to dict
        if name in building:
            logger.warning("Parsing input schema: Self-referential model '%s' detected, treating as dict", name)
            return dict  # type: ignore[return-value]

        building.add(name)
        try:
            props = subschema.get("properties", {})
            reqs = {r for r in (subschema.get("required") or []) if isinstance(r, str)}
            fields: dict[str, Any] = {}

            used_names: set[str] = set()
            wire_names = set(props)
            safe_names = {prop: _safe_field_name(prop, used_names, wire_names) for prop in props}
            reserved_names = wire_names | used_names
            for prop_name, prop_schema in props.items():
                safe_name = safe_names[prop_name]
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
                    field_kwargs["validation_alias"] = _alias_choices(safe_name, prop_name, reserved_names)
                    # Emit the original wire name (including leading underscores)
                    # on model_dump(by_alias=True), not the sanitized field name.
                    field_kwargs["serialization_alias"] = prop_name

                fields[safe_name] = (py_type, Field(default, **field_kwargs))

            # Preserve extras unless schema sets additionalProperties:false (#9881, #10975).
            extra_mode = "ignore" if subschema.get("additionalProperties") is False else "allow"
            model_cls = create_model(name, __config__=ConfigDict(extra=extra_mode), **fields)
        finally:
            building.discard(name)
        model_cache[name] = model_cls
        return model_cls

    # build the top - level "InputSchema" from the root properties
    top_props = schema.get("properties", {})
    top_reqs = {r for r in (schema.get("required") or []) if isinstance(r, str)}
    top_fields: dict[str, Any] = {}

    top_used_names: set[str] = set()
    top_wire_names = set(top_props)
    top_safe_names = {prop: _safe_field_name(prop, top_used_names, top_wire_names) for prop in top_props}
    top_reserved_names = top_wire_names | top_used_names
    for fname, fdef in top_props.items():
        safe_name = top_safe_names[fname]
        py_type = parse_type(fdef)
        if fname not in top_reqs:
            py_type = py_type | None
            default = fdef.get("default", None)
        else:
            default = ...

        # Add alias for camelCase if field name is snake_case
        field_kwargs = {"description": fdef.get("description")}
        if "_" in fname:
            field_kwargs["validation_alias"] = _alias_choices(safe_name, fname, top_reserved_names)
            field_kwargs["serialization_alias"] = fname

        top_fields[safe_name] = (py_type, Field(default, **field_kwargs))

    # Same JSON Schema rule applies at the root: preserve extras unless explicitly forbidden.
    top_extra_mode = "ignore" if schema.get("additionalProperties") is False else "allow"
    return create_model("InputSchema", __config__=ConfigDict(extra=top_extra_mode), **top_fields)
