from enum import Enum
from typing import (
    TypedDict,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

from pydantic import BaseModel, create_model
from typing_extensions import NotRequired


def typed_dict_to_basemodel(name: str, typed_dict: type[TypedDict], created_models: dict = None) -> type[BaseModel]:
    if created_models is None:
        created_models = {}

    # Check if this TypedDict has already been converted to avoid circular references
    if name in created_models:
        return created_models[name]

    # Retrieve type hints (field types) from the TypedDict
    hints = get_type_hints(typed_dict)
    model_fields = {}

    # Determine required and optional fields
    required_keys = getattr(typed_dict, "__required_keys__", set())
    # optional_keys = getattr(typed_dict, "__optional_keys__", set())

    # Helper function to safely check subclass
    def issubclass_safe(cls, classinfo):
        try:
            return issubclass(cls, classinfo)
        except TypeError:
            return False

    # Function to process each type hint recursively
    def process_hint(hint_type):
        origin_inner = get_origin(hint_type)
        args_inner = get_args(hint_type)

        if isinstance(hint_type, type):
            if issubclass_safe(hint_type, TypedDict):
                nested_model_name = f"{hint_type.__name__}Model"
                return typed_dict_to_basemodel(nested_model_name, hint_type, created_models)
            if issubclass_safe(hint_type, BaseModel):
                return hint_type  # Already a Pydantic model
            if issubclass_safe(hint_type, Enum):
                return hint_type  # Enums can be used directly

        if origin_inner in {list, list} and len(args_inner) == 1:
            elem_type = args_inner[0]
            if isinstance(elem_type, type) and issubclass_safe(elem_type, TypedDict):
                nested_model = typed_dict_to_basemodel(f"{elem_type.__name__}Model", elem_type, created_models)
                return list[nested_model]
            return list[elem_type]
        if origin_inner is Union:
            # Handle Optional (Union[..., NoneType])
            non_none_args = [arg for arg in args_inner if arg is not type(None)]
            if len(non_none_args) == 1:
                return process_hint(non_none_args[0]) | None
            return hint_type
        if origin_inner is NotRequired:
            # Handle NotRequired explicitly, treat as Optional
            return args_inner[0] | None
        return hint_type

    for field, hint in hints.items():
        processed_hint = process_hint(hint)

        if field in required_keys:
            model_fields[field] = (processed_hint, ...)
        else:
            # If the field is optional, set default to None
            model_fields[field] = (processed_hint, None)

    # Use Pydantic's create_model to dynamically create the BaseModel
    model = create_model(name, **model_fields)

    created_models[name] = model
    return model
