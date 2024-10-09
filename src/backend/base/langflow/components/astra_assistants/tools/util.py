import asyncio
import inspect
from enum import Enum
import logging
from typing import (
    TypedDict,
    Union,
    get_args,
    get_origin,
    get_type_hints, Type, Dict, Any,
)

from astra_assistants.tools.tool_interface import ToolInterface
from langflow.inputs.inputs import BoolInput, DataInput, DictInput, FloatInput, InputTypes, IntInput, StrInput
from pydantic import BaseModel, create_model, Field
from pydantic_core import PydanticUndefined
from typing_extensions import NotRequired

from langflow.custom import Component
from langflow.template import Output

logger = logging.getLogger(__name__)


# This converts a class structure into a Pydantic BaseModel. Used it for generating flows naively:
# RawGraphDataModel = typed_dict_to_basemodel("GraphDataModel", GraphData)
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


def tool_interface_to_component(tool_cls: Type[ToolInterface]) -> str:
    """
    Generates Python code for a Langflow Component class based on a ToolInterface subclass.

    Args:
        tool_cls (Type[ToolInterface]): The ToolInterface subclass to transform.

    Returns:
        str: The generated Python code for the Component class.
    """

    # Ensure the tool_cls is indeed a subclass of ToolInterface
    if not issubclass(tool_cls, ToolInterface):
        raise TypeError("The provided class must extend ToolInterface.")

    # Derive the component class name by appending 'Component' to the tool class name
    component_class_name = f"{tool_cls.__name__}Component"

    # Extract the 'call' method signature from the tool class
    call_method = tool_cls.call
    call_sig = inspect.signature(call_method)

    # Extract the 'arguments' parameter's type (either a Pydantic BaseModel or a simple string)
    parameters = call_sig.parameters

    # Ensure the 'call' method has exactly one parameter besides 'self'
    if len(parameters) != 2:
        logger.warning(f"The 'call' method must have exactly one parameter, (not counting self). Found {len(parameters)}.")
        return None

    process_inputs_args = []
    # Extract the second parameter (which should be the arguments)
    for param in parameters:
        if param == "self":
            continue
        arguments_param = parameters[param]
        arguments_type = arguments_param.annotation

        # Extract fields from the arguments_type if it's a BaseModel
        argument_fields = {}
        if inspect.isclass(arguments_type) and issubclass(arguments_type, BaseModel):
            argument_fields = arguments_type.model_fields
        else:
            # If the arguments_type is not a BaseModel, we need to add a single field called "arguments"
            argument_fields["arguments"] = Field(any, description="Arguments for the tool")

        # Define inputs based on the argument_fields (only if it's a BaseModel)
        inputs_code = []
        for field_name, field_info in argument_fields.items():
            input_type = field_info.annotation
            # Handle Optional and Union types
            if hasattr(input_type, '__origin__') and input_type.__origin__ is Union:
                # Extract the primary type if it's a Union (e.g., Optional)
                input_type = [arg for arg in input_type.__args__ if arg is not type(None)][0]  # Remove NoneType

            # Map Pydantic types to Langflow InputTypes
            input_class = "StrInput"  # default to StrInput
            if input_type == str:
                input_class = "StrInput"
            elif input_type == int:
                input_class = "IntInput"
            elif input_type == float:
                input_class = "FloatInput"
            elif input_type == bool:
                input_class = "BoolInput"
            elif input_type == dict:
                input_class = "DictInput"
            elif input_type == list:
                input_class = "DataInput"  # Assuming list can be used with DataInput
            # else handle other types as needed

            # Determine if the field is required based on whether it has a default value
            required = field_info.default is PydanticUndefined

            # Add each field as an input to the component
            inputs_code.append(
                f"{input_class}(name='{field_name}', display_name='{field_info.alias or field_name.capitalize()}', required={required})"
            )
            if input_type is None:
                input_type = str
            process_inputs_args.append((field_name,  input_type.__name__))

    # Extract the return type of the 'call' method
    return_annotation = call_sig.return_annotation
    if return_annotation is inspect.Signature.empty or return_annotation is Dict:
        return_annotation = any

    # Check if the return type is either a BaseModel or a string
    if inspect.isclass(return_annotation) and not issubclass(return_annotation, BaseModel):
        return_annotation = any
    elif return_annotation != str and return_annotation != any:
        return_annotation = any

    # Extract fields from the return type if it's a BaseModel
    output_fields = {}
    if inspect.isclass(return_annotation) and issubclass(return_annotation, BaseModel):
        output_fields = return_annotation.model_fields
    else:
        output_fields["result"] = Field(any, description="Result of the tool")

    # Define outputs based on the return type fields (only if it's a BaseModel)
    outputs_code = []
    for field_name, field_info in output_fields.items():
        output_type = field_info.annotation
        # Handle Optional and Union types
        if hasattr(output_type, '__origin__') and output_type.__origin__ is Union:
            # Extract the primary type if it's a Union (e.g., Optional)
            output_type = [arg for arg in output_type.__args__ if arg is not type(None)][0]  # Remove NoneType

        # Map Pydantic types to Langflow Output types
        types = "[\"string\"]"  # default to string
        if output_type == str:
            types = "[\"string\"]"
        elif output_type == int:
            types = "[\"int\"]"
        elif output_type == float:
            types = "[\"float\"]"
        elif output_type == bool:
            types = "[\"bool\"]"
        elif output_type == dict:
            types = "[\"object\"]"
        elif output_type == list:
            types = "[\"array\"]"
        elif output_type == tuple:
            types = "[\"array\"]"
        elif output_type == set:
            types = "[\"array\"]"
        elif output_type == bytes:
            types = "[\"array\"]"

        # Add each output field as an output to the component
        outputs_code.append(
            f"Output(name='{field_name}', display_name='{field_info.alias or field_name.capitalize()}', method='process_inputs', types={types})"
        )

    # Generate the process_inputs method code
    process_inputs_code = f"""
    def process_inputs(self, {', '.join([f"{process_input[0]}: {process_input[1]}" for process_input in process_inputs_args])}) -> Message:
        tool = self.tool_cls({', '.join([process_input[0] for process_input in process_inputs_args])})
        result = tool.call()
        # TODO: handle cases where this is not a string
        return Message(text=result)
    """

    # Generate the complete class code as a string
    component_code = f"""
from typing import Type, Dict, Any, Union
import inspect
from pydantic import BaseModel, Field
from langflow.inputs.inputs import StrInput, IntInput, FloatInput, BoolInput, DictInput, DataInput
from langflow.template import Output
from langflow.schema.message import Message
from langflow.custom import Component
from {tool_cls.__module__} import {tool_cls.__name__}

class {component_class_name}(Component):
    display_name = "{tool_cls.__name__} Component"
    description = "Component for {tool_cls.__name__}."
    icon = "tool_icon"
    name = "{tool_cls.__name__}"
    inputs = [{', '.join(inputs_code)}]
    outputs = [{', '.join(outputs_code)}]
    tool_cls = {tool_cls.__name__}

    {process_inputs_code}
"""

    return component_code
