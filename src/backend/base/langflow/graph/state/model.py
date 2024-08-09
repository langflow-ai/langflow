from typing import Any, Callable, get_type_hints

from pydantic import ConfigDict, computed_field, create_model
from pydantic.fields import FieldInfo


def __validate_method(method: Callable) -> None:
    if not hasattr(method, "__self__"):
        raise ValueError(f"Method {method} does not have a __self__ attribute.")
    if not hasattr(method.__self__, "get_output_by_method"):
        raise ValueError(f"Method's class {method.__self__} must have a get_output_by_method attribute.")


def build_output_getter(method: Callable, validate: bool = True) -> Callable:
    def output_getter(_):
        if validate:
            __validate_method(method)
        methods_class = method.__self__
        output = methods_class.get_output_by_method(method)
        return output.value

    return_type = get_type_hints(method).get("return", None)

    if return_type is None:
        raise ValueError(f"Method {method.__name__} has no return type annotation.")
    output_getter.__annotations__["return"] = return_type
    return output_getter


def build_output_setter(method: Callable, validate: bool = True) -> Callable:
    def output_setter(self, value):
        if validate:
            __validate_method(method)
        methods_class = method.__self__
        output = methods_class.get_output_by_method(method)
        output.value = value

    return output_setter


def create_state_model(model_name: str = "State", validate: bool = True, **kwargs) -> type:
    fields = {}

    for name, value in kwargs.items():
        # Extract the return type from the method's type annotations
        if callable(value):
            # Define the field with the return type
            try:
                __validate_method(value)
                getter = build_output_getter(value, validate)
                setter = build_output_setter(value, validate)
                property_method = property(getter, setter)
            except ValueError as e:
                # If the method is not valid,assume it is already a getter
                if "get_output_by_method" not in str(e) and "__self__" not in str(e):
                    raise e
                property_method = value
            fields[name] = computed_field(property_method)
        elif isinstance(value, FieldInfo):
            field_tuple = (value.annotation or Any, value)
            fields[name] = field_tuple
        elif isinstance(value, tuple) and len(value) == 2:
            # Fields are defined by one of the following tuple forms:

            # (<type>, <default value>)
            # (<type>, Field(...))
            # typing.Annotated[<type>, Field(...)]
            if not isinstance(value[0], type):
                raise ValueError(f"Invalid type for field {name}: {type(value[0])}")
            fields[name] = (value[0], value[1])
        else:
            raise ValueError(f"Invalid value type {type(value)} for field {name}")

    # Create the model dynamically
    config_dict = ConfigDict(arbitrary_types_allowed=True, validate_assignment=True)
    model = create_model(model_name, __config__=config_dict, **fields)

    return model
