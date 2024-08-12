from typing import Any, Callable, get_type_hints

from pydantic import ConfigDict, computed_field, create_model
from pydantic.fields import FieldInfo


def __validate_method(method: Callable) -> None:
    """
    Validates a method by checking if it has the required attributes.

    This function ensures that the given method belongs to a class with the necessary
    structure for output handling. It checks for the presence of a __self__ attribute
    on the method and a get_output_by_method attribute on the method's class.

    Args:
        method (Callable): The method to be validated.

    Raises:
        ValueError: If the method does not have a __self__ attribute or if the method's
                    class does not have a get_output_by_method attribute.

    Example:
        >>> class ValidClass:
        ...     def get_output_by_method(self):
        ...         pass
        ...     def valid_method(self):
        ...         pass
        >>> __validate_method(ValidClass().valid_method)  # This will pass
        >>> __validate_method(lambda x: x)  # This will raise a ValueError
    """
    if not hasattr(method, "__self__"):
        raise ValueError(f"Method {method} does not have a __self__ attribute.")
    if not hasattr(method.__self__, "get_output_by_method"):
        raise ValueError(f"Method's class {method.__self__} must have a get_output_by_method attribute.")


def build_output_getter(method: Callable, validate: bool = True) -> Callable:
    """
    Builds an output getter function for a given method in a graph component.

    This function creates a new callable that, when invoked, retrieves the output
    of the specified method using the get_output_by_method of the method's class.
    It's used in creating dynamic state models for graph components.

    Args:
        method (Callable): The method for which to build the output getter.
        validate (bool, optional): Whether to validate the method before building
                                   the getter. Defaults to True.

    Returns:
        Callable: The output getter function. When called, this function returns
                  the value of the output associated with the original method.

    Raises:
        ValueError: If the method has no return type annotation or if validation fails.

    Notes:
        - The getter function returns UNDEFINED if the output has not been set.
        - When validate is True, the method must belong to a class with a
          'get_output_by_method' attribute.
        - This function is typically used internally by create_state_model.

    Example:
        >>> class ChatComponent:
        ...     def get_output_by_method(self, method):
        ...         return type('Output', (), {'value': "Hello, World!"})()
        ...     def get_message(self) -> str:
        ...         pass
        >>> component = ChatComponent()
        >>> getter = build_output_getter(component.get_message)
        >>> print(getter(None))  # This will print "Hello, World!"
    """

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
                if "get_output_by_method" not in str(e) and "__self__" not in str(e) or validate:
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
