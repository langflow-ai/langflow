from types import UnionType
from typing import Any, Literal, Union, get_args, get_origin

from pydantic import BaseModel, Field, create_model

from lfx.inputs.input_mixin import FieldTypes
from lfx.inputs.inputs import (
    BoolInput,
    DictInput,
    DropdownInput,
    FloatInput,
    InputTypes,
    IntInput,
    MessageTextInput,
)
from lfx.schema.dotdict import dotdict

_convert_field_type_to_type: dict[FieldTypes, type] = {
    FieldTypes.TEXT: str,
    FieldTypes.INTEGER: int,
    FieldTypes.FLOAT: float,
    FieldTypes.BOOLEAN: bool,
    FieldTypes.DICT: dict,
    FieldTypes.NESTED_DICT: dict,
    FieldTypes.TABLE: dict,
    FieldTypes.FILE: str,
    FieldTypes.PROMPT: str,
    FieldTypes.CODE: str,
    FieldTypes.OTHER: str,
    FieldTypes.TAB: str,
    FieldTypes.QUERY: str,
}


_convert_type_to_field_type = {
    str: MessageTextInput,
    int: IntInput,
    float: FloatInput,
    bool: BoolInput,
    dict: DictInput,
    list: MessageTextInput,
}


def flatten_schema(root_schema: dict[str, Any]) -> dict[str, Any]:
    """Flatten a JSON RPC style schema into a single level JSON Schema.

    If the input schema is already flat (no $defs / $ref / nested objects or arrays)
    the function simply returns the original i.e. a noop.
    """
    defs = root_schema.get("$defs", {})

    # --- Fast path: schema is already flat ---------------------------------
    props = root_schema.get("properties", {})
    if not defs and all("$ref" not in v and v.get("type") not in ("object", "array") for v in props.values()):
        return root_schema
    # -----------------------------------------------------------------------

    flat_props: dict[str, dict[str, Any]] = {}
    required_list: list[str] = []

    def _resolve_if_ref(schema: dict[str, Any]) -> dict[str, Any]:
        while "$ref" in schema:
            ref_name = schema["$ref"].split("/")[-1]
            schema = defs.get(ref_name, {})
        return schema

    def _walk(name: str, schema: dict[str, Any], *, inherited_req: bool) -> None:
        schema = _resolve_if_ref(schema)
        t = schema.get("type")

        # ── objects ─────────────────────────────────────────────────────────
        if t == "object":
            req_here = set(schema.get("required", []))
            for k, subschema in schema.get("properties", {}).items():
                child_name = f"{name}.{k}" if name else k
                _walk(name=child_name, schema=subschema, inherited_req=inherited_req and k in req_here)
            return

        # ── arrays (always recurse into the first item as "[0]") ───────────
        if t == "array":
            items = schema.get("items", {})
            _walk(name=f"{name}[0]", schema=items, inherited_req=inherited_req)
            return

        leaf: dict[str, Any] = {
            k: v
            for k, v in schema.items()
            if k
            in (
                "type",
                "description",
                "pattern",
                "format",
                "enum",
                "default",
                "minLength",
                "maxLength",
                "minimum",
                "maximum",
                "exclusiveMinimum",
                "exclusiveMaximum",
                "additionalProperties",
                "examples",
            )
        }
        flat_props[name] = leaf
        if inherited_req:
            required_list.append(name)

    # kick things off at the true root
    root_required = set(root_schema.get("required", []))
    for k, subschema in props.items():
        _walk(k, subschema, inherited_req=k in root_required)

    # build the flattened schema; keep any descriptive metadata
    result: dict[str, Any] = {
        "type": "object",
        "properties": flat_props,
        **{k: v for k, v in root_schema.items() if k not in ("properties", "$defs")},
    }
    if required_list:
        result["required"] = required_list
    return result


def schema_to_langflow_inputs(schema: type[BaseModel]) -> list[InputTypes]:
    inputs: list[InputTypes] = []

    for field_name, model_field in schema.model_fields.items():
        ann = model_field.annotation
        if isinstance(ann, UnionType):
            # Extract non-None types from Union
            non_none_types = [t for t in get_args(ann) if t is not type(None)]
            if len(non_none_types) == 1:
                ann = non_none_types[0]

        is_list = False

        if get_origin(ann) is list:
            is_list = True
            ann = get_args(ann)[0]

        options: list[Any] | None = None
        if get_origin(ann) is Literal:
            options = list(get_args(ann))
            if options:
                ann = type(options[0])

        if get_origin(ann) is Union:
            non_none = [t for t in get_args(ann) if t is not type(None)]
            if len(non_none) == 1:
                ann = non_none[0]

        # 2) Enumerated choices
        if options is not None:
            inputs.append(
                DropdownInput(
                    display_name=model_field.title or field_name.replace("_", " ").title(),
                    name=field_name,
                    info=model_field.description or "",
                    required=model_field.is_required(),
                    is_list=is_list,
                    options=options,
                )
            )
            continue

        # 3) "Any" fallback → text
        if ann is Any:
            inputs.append(
                MessageTextInput(
                    display_name=model_field.title or field_name.replace("_", " ").title(),
                    name=field_name,
                    info=model_field.description or "",
                    required=model_field.is_required(),
                    is_list=is_list,
                )
            )
            continue

        # 4) Primitive via your mapping
        try:
            lf_cls = _convert_type_to_field_type[ann]
        except KeyError as err:
            msg = f"Unsupported field type: {ann}"
            raise TypeError(msg) from err
        inputs.append(
            lf_cls(
                display_name=model_field.title or field_name.replace("_", " ").title(),
                name=field_name,
                info=model_field.description or "",
                required=model_field.is_required(),
                is_list=is_list,
            )
        )

    return inputs


def create_input_schema(inputs: list["InputTypes"]) -> type[BaseModel]:
    if not isinstance(inputs, list):
        msg = "inputs must be a list of Inputs"
        raise TypeError(msg)
    fields = {}
    for input_model in inputs:
        # Create a Pydantic Field for each input field
        field_type = input_model.field_type
        if isinstance(field_type, FieldTypes):
            field_type = _convert_field_type_to_type[field_type]
        else:
            msg = f"Invalid field type: {field_type}"
            raise TypeError(msg)
        if hasattr(input_model, "options") and isinstance(input_model.options, list) and input_model.options:
            literal_string = f"Literal{input_model.options}"
            # validate that the literal_string is a valid literal

            field_type = eval(literal_string, {"Literal": Literal})  # noqa: S307
        if hasattr(input_model, "is_list") and input_model.is_list:
            field_type = list[field_type]  # type: ignore[valid-type]
        if input_model.name:
            name = input_model.name.replace("_", " ").title()
        elif input_model.display_name:
            name = input_model.display_name
        else:
            msg = "Input name or display_name is required"
            raise ValueError(msg)
        field_dict = {
            "title": name,
            "description": input_model.info or "",
        }
        if input_model.required is False:
            field_dict["default"] = input_model.value  # type: ignore[assignment]
        pydantic_field = Field(**field_dict)

        fields[input_model.name] = (field_type, pydantic_field)

    # Create and return the InputSchema model
    model = create_model("InputSchema", **fields)
    model.model_rebuild()
    return model


def create_input_schema_from_dict(inputs: list[dotdict], param_key: str | None = None) -> type[BaseModel]:
    if not isinstance(inputs, list):
        msg = "inputs must be a list of Inputs"
        raise TypeError(msg)
    fields = {}
    for input_model in inputs:
        # Create a Pydantic Field for each input field
        field_type = input_model.type
        if hasattr(input_model, "options") and isinstance(input_model.options, list) and input_model.options:
            literal_string = f"Literal{input_model.options}"
            # validate that the literal_string is a valid literal

            field_type = eval(literal_string, {"Literal": Literal})  # noqa: S307
        if hasattr(input_model, "is_list") and input_model.is_list:
            field_type = list[field_type]  # type: ignore[valid-type]
        if input_model.name:
            name = input_model.name.replace("_", " ").title()
        elif input_model.display_name:
            name = input_model.display_name
        else:
            msg = "Input name or display_name is required"
            raise ValueError(msg)
        field_dict = {
            "title": name,
            "description": input_model.info or "",
        }
        if input_model.required is False:
            field_dict["default"] = input_model.value  # type: ignore[assignment]
        pydantic_field = Field(**field_dict)

        fields[input_model.name] = (field_type, pydantic_field)

    # Wrap fields in a dictionary with the key as param_key
    if param_key is not None:
        # Create an inner model with the fields
        inner_model = create_model("InnerModel", **fields)

        # Ensure the model is wrapped correctly in a dictionary
        # model = create_model("InputSchema", **{param_key: (inner_model, Field(default=..., description=description))})
        model = create_model("InputSchema", **{param_key: (inner_model, ...)})
    else:
        # Create and return the InputSchema model
        model = create_model("InputSchema", **fields)

    model.model_rebuild()
    return model
