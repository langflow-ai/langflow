from collections.abc import Callable
from typing import Any, get_type_hints

from pydantic import ConfigDict, computed_field, create_model
from pydantic.fields import FieldInfo


def __validate_method(method: Callable) -> None:
    """Validates a method by checking if it has the required attributes.

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
        msg = f"Method {method} does not have a __self__ attribute."
        raise ValueError(msg)
    if not hasattr(method.__self__, "get_output_by_method"):
        msg = f"Method's class {method.__self__} must have a get_output_by_method attribute."
        raise ValueError(msg)


def build_output_getter(method: Callable, *, validate: bool = True) -> Callable:
    """Builds an output getter function for a given method in a graph component.

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
        msg = f"Method {method.__name__} has no return type annotation."
        raise ValueError(msg)
    output_getter.__annotations__["return"] = return_type
    return output_getter


def build_output_setter(method: Callable, *, validate: bool = True) -> Callable:
    """Build an output setter function for a given method in a graph component.

    This function creates a new callable that, when invoked, sets the output
    of the specified method using the get_output_by_method of the method's class.
    It's used in creating dynamic state models for graph components, allowing
    for the modification of component states.

    Args:
        method (Callable): The method for which the output setter is being built.
        validate (bool, optional): Flag indicating whether to validate the method
                                   before building the setter. Defaults to True.

    Returns:
        Callable: The output setter function. When called with a value, this function
                  sets the output associated with the original method to that value.

    Raises:
        ValueError: If validation fails when validate is True.

    Notes:
        - When validate is True, the method must belong to a class with a
          'get_output_by_method' attribute.
        - This function is typically used internally by create_state_model.
        - The setter allows for dynamic updating of component states in a graph.

    Example:
        >>> class ChatComponent:
        ...     def get_output_by_method(self, method):
        ...         return type('Output', (), {'value': None})()
        ...     def set_message(self):
        ...         pass
        >>> component = ChatComponent()
        >>> setter = build_output_setter(component.set_message)
        >>> setter(component, "New message")
        >>> print(component.get_output_by_method(component.set_message).value)  # Prints "New message"
    """

    def output_setter(self, value) -> None:  # noqa: ARG001
        if validate:
            __validate_method(method)
        methods_class = method.__self__  # type: ignore[attr-defined]
        output = methods_class.get_output_by_method(method)
        output.value = value

    return output_setter


def create_state_model(model_name: str = "State", *, validate: bool = True, **kwargs) -> type:
    """Create a dynamic Pydantic state model based on the provided keyword arguments.

    This function generates a Pydantic model class with fields corresponding to the
    provided keyword arguments. It can handle various types of field definitions,
    including callable methods (which are converted to properties), FieldInfo objects,
    and type-default value tuples.

    Args:
        model_name (str, optional): The name of the model. Defaults to "State".
        validate (bool, optional): Whether to validate the methods when converting
                                   them to properties. Defaults to True.
        **kwargs: Keyword arguments representing the fields of the model. Each argument
                  can be a callable method, a FieldInfo object, or a tuple of (type, default).

    Returns:
        type: The dynamically created Pydantic state model class.

    Raises:
        ValueError: If the provided field value is invalid or cannot be processed.

    Examples:
        >>> from lfx.components.io import ChatInput
        >>> from lfx.components.io.ChatOutput import ChatOutput
        >>> from pydantic import Field
        >>>
        >>> chat_input = ChatInput()
        >>> chat_output = ChatOutput()
        >>>
        >>> # Create a model with a method from a component
        >>> StateModel = create_state_model(method_one=chat_input.message_response)
        >>> state = StateModel()
        >>> assert state.method_one is UNDEFINED
        >>> chat_input.set_output_value("message", "test")
        >>> assert state.method_one == "test"
        >>>
        >>> # Create a model with multiple components and a Pydantic Field
        >>> NewStateModel = create_state_model(
        ...     model_name="NewStateModel",
        ...     first_method=chat_input.message_response,
        ...     second_method=chat_output.message_response,
        ...     my_attribute=Field(None)
        ... )
        >>> new_state = NewStateModel()
        >>> new_state.first_method = "test"
        >>> new_state.my_attribute = 123
        >>> assert new_state.first_method == "test"
        >>> assert new_state.my_attribute == 123
        >>>
        >>> # Create a model with tuple-based field definitions
        >>> TupleStateModel = create_state_model(field_one=(str, "default"), field_two=(int, 123))
        >>> tuple_state = TupleStateModel()
        >>> assert tuple_state.field_one == "default"
        >>> assert tuple_state.field_two == 123

    Notes:
        - The function handles empty keyword arguments gracefully.
        - For tuple-based field definitions, the first element must be a valid Python type.
        - Unsupported value types in keyword arguments will raise a ValueError.
        - Callable methods must have proper return type annotations and belong to a class
          with a 'get_output_by_method' attribute when validate is True.
    """
    fields = {}

    for name, value in kwargs.items():
        # Extract the return type from the method's type annotations
        if callable(value):
            # Define the field with the return type
            try:
                __validate_method(value)
                getter = build_output_getter(value, validate=validate)
                setter = build_output_setter(value, validate=validate)
                property_method = property(getter, setter)
            except ValueError as e:
                # If the method is not valid,assume it is already a getter
                if ("get_output_by_method" not in str(e) and "__self__" not in str(e)) or validate:
                    raise
                property_method = value
            fields[name] = computed_field(property_method)
        elif isinstance(value, FieldInfo):
            field_tuple = (value.annotation or Any, value)
            fields[name] = field_tuple
        elif isinstance(value, tuple) and len(value) == 2:  # noqa: PLR2004
            # Fields are defined by one of the following tuple forms:

            # (<type>, <default value>)
            # (<type>, Field(...))
            # typing.Annotated[<type>, Field(...)]
            if not isinstance(value[0], type):
                msg = f"Invalid type for field {name}: {type(value[0])}"
                raise TypeError(msg)
            fields[name] = (value[0], value[1])
        else:
            msg = f"Invalid value type {type(value)} for field {name}"
            raise ValueError(msg)

    # Create the model dynamically
    config_dict = ConfigDict(arbitrary_types_allowed=True, validate_assignment=True)
    return create_model(model_name, __config__=config_dict, **fields)
