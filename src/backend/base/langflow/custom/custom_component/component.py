from __future__ import annotations

import ast
import asyncio
import inspect
from collections.abc import AsyncIterator, Iterator
from copy import deepcopy
from textwrap import dedent
from typing import TYPE_CHECKING, Any, ClassVar, NamedTuple, get_type_hints
from uuid import UUID

import nanoid
import pandas as pd
import yaml
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ValidationError

from langflow.base.tools.constants import (
    TOOL_OUTPUT_DISPLAY_NAME,
    TOOL_OUTPUT_NAME,
    TOOLS_METADATA_INFO,
    TOOLS_METADATA_INPUT_NAME,
)
from langflow.custom.tree_visitor import RequiredInputsVisitor
from langflow.exceptions.component import StreamingError
from langflow.field_typing import Tool  # noqa: TC001 Needed by _add_toolkit_output
from langflow.graph.state.model import create_state_model
from langflow.graph.utils import has_chat_output
from langflow.helpers.custom import format_type
from langflow.memory import astore_message, aupdate_messages, delete_message
from langflow.schema.artifact import get_artifact_type, post_process_raw
from langflow.schema.data import Data
from langflow.schema.message import ErrorMessage, Message
from langflow.schema.properties import Source
from langflow.services.deps import get_db_service
from langflow.services.tracing.schema import Log
from langflow.template.field.base import UNDEFINED, Input, Output
from langflow.template.frontend_node.custom_components import ComponentFrontendNode
from langflow.utils.async_helpers import run_until_complete
from langflow.utils.util import find_closest_match

from .custom_component import CustomComponent

if TYPE_CHECKING:
    from collections.abc import Callable

    from langflow.base.tools.component_tool import ComponentToolkit
    from langflow.events.event_manager import EventManager
    from langflow.graph.edge.schema import EdgeData
    from langflow.graph.vertex.base import Vertex
    from langflow.inputs.inputs import InputTypes
    from langflow.schema.dataframe import DataFrame
    from langflow.schema.log import LoggableType


_ComponentToolkit = None


def _get_component_toolkit():
    global _ComponentToolkit  # noqa: PLW0603
    if _ComponentToolkit is None:
        from langflow.base.tools.component_tool import ComponentToolkit

        _ComponentToolkit = ComponentToolkit
    return _ComponentToolkit


BACKWARDS_COMPATIBLE_ATTRIBUTES = ["user_id", "vertex", "tracing_service"]
CONFIG_ATTRIBUTES = ["_display_name", "_description", "_icon", "_name", "_metadata"]


class PlaceholderGraph(NamedTuple):
    """A placeholder graph structure for components, providing backwards compatibility.

    and enabling component execution without a full graph object.

    This lightweight structure contains essential information typically found in a complete graph,
    allowing components to function in isolation or in simplified contexts.

    Attributes:
        flow_id (str | None): Unique identifier for the flow, if applicable.
        user_id (str | None): Identifier of the user associated with the flow, if any.
        session_id (str | None): Identifier for the current session, if applicable.
        context (dict): Additional contextual information for the component's execution.
        flow_name (str | None): Name of the flow, if available.
    """

    flow_id: str | None
    user_id: str | None
    session_id: str | None
    context: dict
    flow_name: str | None


class Component(CustomComponent):
    inputs: list[InputTypes] = []
    outputs: list[Output] = []
    selected_output: str | None = None
    code_class_base_inheritance: ClassVar[str] = "Component"

    def __init__(self, **kwargs) -> None:
        # Initialize instance-specific attributes first
        if overlap := self._there_is_overlap_in_inputs_and_outputs():
            msg = f"Inputs and outputs have overlapping names: {overlap}"
            raise ValueError(msg)
        self._output_logs: dict[str, list[Log]] = {}
        self._current_output: str = ""
        self._metadata: dict = {}
        self._ctx: dict = {}
        self._code: str | None = None
        self._logs: list[Log] = []

        # Initialize component-specific collections
        self._inputs: dict[str, InputTypes] = {}
        self._outputs_map: dict[str, Output] = {}
        self._results: dict[str, Any] = {}
        self._attributes: dict[str, Any] = {}
        self._edges: list[EdgeData] = []
        self._components: list[Component] = []
        self._event_manager: EventManager | None = None
        self._state_model = None

        # Process input kwargs
        inputs = {}
        config = {}
        for key, value in kwargs.items():
            if key.startswith("_"):
                config[key] = value
            elif key in CONFIG_ATTRIBUTES:
                config[key[1:]] = value
            else:
                inputs[key] = value

        self._parameters = inputs or {}
        self.set_attributes(self._parameters)

        # Store original inputs and config for reference
        self.__inputs = inputs
        self.__config = config or {}

        # Add unique ID if not provided
        if "_id" not in self.__config:
            self.__config |= {"_id": f"{self.__class__.__name__}-{nanoid.generate(size=5)}"}

        # Initialize base class
        super().__init__(**self.__config)

        # Post-initialization setup
        if hasattr(self, "_trace_type"):
            self.trace_type = self._trace_type
        if not hasattr(self, "trace_type"):
            self.trace_type = "chain"

        # Setup inputs and outputs
        self._reset_all_output_values()
        if self.inputs is not None:
            self.map_inputs(self.inputs)
        self.map_outputs()

        # Final setup
        self._set_output_types(list(self._outputs_map.values()))
        self.set_class_code()
        self._set_output_required_inputs()
        self._database_available: bool | None = None

    def _build_source(self, id_: str | None, display_name: str | None, source: str | None) -> Source:
        source_dict = {}
        if id_:
            source_dict["id"] = id_
        if display_name:
            source_dict["display_name"] = display_name
        if source:
            # Handle case where source is a ChatOpenAI and other models objects
            if hasattr(source, "model_name"):
                source_dict["source"] = source.model_name
            elif hasattr(source, "model"):
                source_dict["source"] = str(source.model)
            else:
                source_dict["source"] = str(source)
        return Source(**source_dict)

    def get_incoming_edge_by_target_param(self, target_param: str) -> str | None:
        """Get the source vertex ID for an incoming edge that targets a specific parameter.

        This method delegates to the underlying vertex to find an incoming edge that connects
        to the specified target parameter.

        Args:
            target_param (str): The name of the target parameter to find an incoming edge for

        Returns:
            str | None: The ID of the source vertex if an incoming edge is found, None otherwise
        """
        if self._vertex is None:
            msg = "Vertex not found. Please build the graph first."
            raise ValueError(msg)
        return self._vertex.get_incoming_edge_by_target_param(target_param)

    @property
    def enabled_tools(self) -> list[str] | None:
        """Dynamically determine which tools should be enabled.

        This property can be overridden by subclasses to provide custom tool filtering.
        By default, it returns None, which means all tools are enabled.

        Returns:
            list[str] | None: List of tool names or tags to enable, or None to enable all tools.
        """
        # Default implementation returns None (all tools enabled)
        # Subclasses can override this to provide custom filtering
        return None

    def _there_is_overlap_in_inputs_and_outputs(self) -> set[str]:
        """Check the `.name` of inputs and outputs to see if there is overlap.

        Returns:
            set[str]: Set of names that overlap between inputs and outputs.
        """
        # Create sets of input and output names for O(1) lookup
        input_names = {input_.name for input_ in self.inputs if input_.name is not None}
        output_names = {output.name for output in self.outputs}

        # Return the intersection of the sets
        return input_names & output_names

    def get_base_args(self):
        """Get the base arguments required for component initialization.

        Returns:
            dict: A dictionary containing the base arguments:
                - _user_id: The ID of the current user
                - _session_id: The ID of the current session
                - _tracing_service: The tracing service instance for logging/monitoring
        """
        return {
            "_user_id": self.user_id,
            "_session_id": self.graph.session_id,
            "_tracing_service": self._tracing_service,
        }

    @property
    def ctx(self):
        if not hasattr(self, "graph") or self.graph is None:
            msg = "Graph not found. Please build the graph first."
            raise ValueError(msg)
        return self.graph.context

    def add_to_ctx(self, key: str, value: Any, *, overwrite: bool = False) -> None:
        """Add a key-value pair to the context.

        Args:
            key (str): The key to add.
            value (Any): The value to associate with the key.
            overwrite (bool, optional): Whether to overwrite the existing value. Defaults to False.

        Raises:
            ValueError: If the graph is not built.
        """
        if not hasattr(self, "graph") or self.graph is None:
            msg = "Graph not found. Please build the graph first."
            raise ValueError(msg)
        if key in self.graph.context and not overwrite:
            msg = f"Key {key} already exists in context. Set overwrite=True to overwrite."
            raise ValueError(msg)
        self.graph.context.update({key: value})

    def update_ctx(self, value_dict: dict[str, Any]) -> None:
        """Update the context with a dictionary of values.

        Args:
            value_dict (dict[str, Any]): The dictionary of values to update.

        Raises:
            ValueError: If the graph is not built.
        """
        if not hasattr(self, "graph") or self.graph is None:
            msg = "Graph not found. Please build the graph first."
            raise ValueError(msg)
        if not isinstance(value_dict, dict):
            msg = "Value dict must be a dictionary"
            raise TypeError(msg)

        self.graph.context.update(value_dict)

    def _pre_run_setup(self):
        pass

    def set_event_manager(self, event_manager: EventManager | None = None) -> None:
        self._event_manager = event_manager

    def _reset_all_output_values(self) -> None:
        if isinstance(self._outputs_map, dict):
            for output in self._outputs_map.values():
                output.value = UNDEFINED

    def _build_state_model(self):
        if self._state_model:
            return self._state_model
        name = self.name or self.__class__.__name__
        model_name = f"{name}StateModel"
        fields = {}
        for output in self._outputs_map.values():
            fields[output.name] = getattr(self, output.method)
        self._state_model = create_state_model(model_name=model_name, **fields)
        return self._state_model

    def get_state_model_instance_getter(self):
        state_model = self._build_state_model()

        def _instance_getter(_):
            return state_model()

        _instance_getter.__annotations__["return"] = state_model
        return _instance_getter

    def __deepcopy__(self, memo: dict) -> Component:
        if id(self) in memo:
            return memo[id(self)]
        kwargs = deepcopy(self.__config, memo)
        kwargs["inputs"] = deepcopy(self.__inputs, memo)
        new_component = type(self)(**kwargs)
        new_component._code = self._code
        new_component._outputs_map = self._outputs_map
        new_component._inputs = self._inputs
        new_component._edges = self._edges
        new_component._components = self._components
        new_component._parameters = self._parameters
        new_component._attributes = self._attributes
        new_component._output_logs = self._output_logs
        new_component._logs = self._logs  # type: ignore[attr-defined]
        memo[id(self)] = new_component
        return new_component

    def set_class_code(self) -> None:
        # Get the source code of the calling class
        if self._code:
            return
        try:
            module = inspect.getmodule(self.__class__)
            if module is None:
                msg = "Could not find module for class"
                raise ValueError(msg)

            class_code = inspect.getsource(module)
            self._code = class_code
        except (OSError, TypeError) as e:
            msg = f"Could not find source code for {self.__class__.__name__}"
            raise ValueError(msg) from e

    def set(self, **kwargs):
        """Connects the component to other components or sets parameters and attributes.

        Args:
            **kwargs: Keyword arguments representing the connections, parameters, and attributes.

        Returns:
            None

        Raises:
            KeyError: If the specified input name does not exist.
        """
        for key, value in kwargs.items():
            self._process_connection_or_parameters(key, value)
        return self

    def list_inputs(self):
        """Returns a list of input names."""
        return [_input.name for _input in self.inputs]

    def list_outputs(self):
        """Returns a list of output names."""
        return [_output.name for _output in self._outputs_map.values()]

    async def run(self):
        """Executes the component's logic and returns the result.

        Returns:
            The result of executing the component's logic.
        """
        return await self._run()

    def set_vertex(self, vertex: Vertex) -> None:
        """Sets the vertex for the component.

        Args:
            vertex (Vertex): The vertex to set.

        Returns:
            None
        """
        self._vertex = vertex

    def get_input(self, name: str) -> Any:
        """Retrieves the value of the input with the specified name.

        Args:
            name (str): The name of the input.

        Returns:
            Any: The value of the input.

        Raises:
            ValueError: If the input with the specified name is not found.
        """
        if name in self._inputs:
            return self._inputs[name]
        msg = f"Input {name} not found in {self.__class__.__name__}"
        raise ValueError(msg)

    def get_output(self, name: str) -> Any:
        """Retrieves the output with the specified name.

        Args:
            name (str): The name of the output to retrieve.

        Returns:
            Any: The output value.

        Raises:
            ValueError: If the output with the specified name is not found.
        """
        if name in self._outputs_map:
            return self._outputs_map[name]
        msg = f"Output {name} not found in {self.__class__.__name__}"
        raise ValueError(msg)

    def set_on_output(self, name: str, **kwargs) -> None:
        output = self.get_output(name)
        for key, value in kwargs.items():
            if not hasattr(output, key):
                msg = f"Output {name} does not have a method {key}"
                raise ValueError(msg)
            setattr(output, key, value)

    def set_output_value(self, name: str, value: Any) -> None:
        if name in self._outputs_map:
            self._outputs_map[name].value = value
        else:
            msg = f"Output {name} not found in {self.__class__.__name__}"
            raise ValueError(msg)

    def map_outputs(self) -> None:
        """Maps the given list of outputs to the component.

        Args:
            outputs (List[Output]): The list of outputs to be mapped.

        Raises:
            ValueError: If the output name is None.

        Returns:
            None
        """
        # override outputs (generated from the class code) with vertex outputs
        # if they exist (generated from the frontend)
        outputs = []
        if self._vertex and self._vertex.outputs:
            for output in self._vertex.outputs:
                try:
                    output_ = Output(**output)
                    outputs.append(output_)
                except ValidationError as e:
                    msg = f"Invalid output: {e}"
                    raise ValueError(msg) from e
        else:
            outputs = self.outputs
        for output in outputs:
            if output.name is None:
                msg = "Output name cannot be None."
                raise ValueError(msg)
            # Deepcopy is required to avoid modifying the original component;
            # allows each instance of each component to modify its own output
            self._outputs_map[output.name] = deepcopy(output)

    def map_inputs(self, inputs: list[InputTypes]) -> None:
        """Maps the given inputs to the component.

        Args:
            inputs (List[InputTypes]): A list of InputTypes objects representing the inputs.

        Raises:
            ValueError: If the input name is None.

        """
        for input_ in inputs:
            if input_.name is None:
                msg = self.build_component_error_message("Input name cannot be None")
                raise ValueError(msg)
            try:
                self._inputs[input_.name] = deepcopy(input_)
            except TypeError:
                self._inputs[input_.name] = input_

    def validate(self, params: dict) -> None:
        """Validates the component parameters.

        Args:
            params (dict): A dictionary containing the component parameters.

        Raises:
            ValueError: If the inputs are not valid.
            ValueError: If the outputs are not valid.
        """
        self._validate_inputs(params)
        self._validate_outputs()

    async def run_and_validate_update_outputs(self, frontend_node: dict, field_name: str, field_value: Any):
        frontend_node = self.update_outputs(frontend_node, field_name, field_value)
        if field_name == "tool_mode" or frontend_node.get("tool_mode"):
            is_tool_mode = field_value or frontend_node.get("tool_mode")
            frontend_node["outputs"] = [self._build_tool_output()] if is_tool_mode else frontend_node["outputs"]
            if is_tool_mode:
                frontend_node.setdefault("template", {})
                frontend_node["tool_mode"] = True
                tools_metadata_input = await self._build_tools_metadata_input()
                frontend_node["template"][TOOLS_METADATA_INPUT_NAME] = tools_metadata_input.to_dict()
                self._append_tool_to_outputs_map()
            elif "template" in frontend_node:
                frontend_node["template"].pop(TOOLS_METADATA_INPUT_NAME, None)
        self.tools_metadata = frontend_node.get("template", {}).get(TOOLS_METADATA_INPUT_NAME, {}).get("value")
        return self._validate_frontend_node(frontend_node)

    def _validate_frontend_node(self, frontend_node: dict):
        # Check if all outputs are either Output or a valid Output model
        for index, output in enumerate(frontend_node["outputs"]):
            if isinstance(output, dict):
                try:
                    output_ = Output(**output)
                    self._set_output_return_type(output_)
                    output_dict = output_.model_dump()
                except ValidationError as e:
                    msg = f"Invalid output: {e}"
                    raise ValueError(msg) from e
            elif isinstance(output, Output):
                # we need to serialize it
                self._set_output_return_type(output)
                output_dict = output.model_dump()
            else:
                msg = f"Invalid output type: {type(output)}"
                raise TypeError(msg)
            frontend_node["outputs"][index] = output_dict
        return frontend_node

    def update_outputs(self, frontend_node: dict, field_name: str, field_value: Any) -> dict:  # noqa: ARG002
        """Default implementation for updating outputs based on field changes.

        Subclasses can override this to modify outputs based on field_name and field_value.
        """
        return frontend_node

    def _set_output_types(self, outputs: list[Output]) -> None:
        for output in outputs:
            self._set_output_return_type(output)

    def _set_output_return_type(self, output: Output) -> None:
        if output.method is None:
            msg = f"Output {output.name} does not have a method"
            raise ValueError(msg)
        return_types = self._get_method_return_type(output.method)
        output.add_types(return_types)

    def _set_output_required_inputs(self) -> None:
        for output in self.outputs:
            if not output.method:
                continue
            method = getattr(self, output.method, None)
            if not method or not callable(method):
                continue
            try:
                source_code = inspect.getsource(method)
                ast_tree = ast.parse(dedent(source_code))
            except Exception:  # noqa: BLE001
                ast_tree = ast.parse(dedent(self._code or ""))

            visitor = RequiredInputsVisitor(self._inputs)
            visitor.visit(ast_tree)
            output.required_inputs = sorted(visitor.required_inputs)

    def get_output_by_method(self, method: Callable):
        # method is a callable and output.method is a string
        # we need to find the output that has the same method
        output = next((output for output in self._outputs_map.values() if output.method == method.__name__), None)
        if output is None:
            method_name = method.__name__ if hasattr(method, "__name__") else str(method)
            msg = f"Output with method {method_name} not found"
            raise ValueError(msg)
        return output

    def _inherits_from_component(self, method: Callable):
        # check if the method is a method from a class that inherits from Component
        # and that it is an output of that class
        return hasattr(method, "__self__") and isinstance(method.__self__, Component)

    def _method_is_valid_output(self, method: Callable):
        # check if the method is a method from a class that inherits from Component
        # and that it is an output of that class
        return (
            hasattr(method, "__self__")
            and isinstance(method.__self__, Component)
            and method.__self__.get_output_by_method(method)
        )

    def _build_error_string_from_matching_pairs(self, matching_pairs: list[tuple[Output, Input]]):
        text = ""
        for output, input_ in matching_pairs:
            text += f"{output.name}[{','.join(output.types)}]->{input_.name}[{','.join(input_.input_types or [])}]\n"
        return text

    def _find_matching_output_method(self, input_name: str, value: Component):
        """Find the output method from the given component and input name.

        Find the output method from the given component (`value`) that matches the specified input (`input_name`)
        in the current component.
        This method searches through all outputs of the provided component to find outputs whose types match
        the input types of the specified input in the current component. If exactly one matching output is found,
        it returns the corresponding method. If multiple matching outputs are found, it raises an error indicating
        ambiguity. If no matching outputs are found, it raises an error indicating that no suitable output was found.

        Args:
            input_name (str): The name of the input in the current component to match.
            value (Component): The component whose outputs are to be considered.

        Returns:
            Callable: The method corresponding to the matching output.

        Raises:
            ValueError: If multiple matching outputs are found, if no matching outputs are found,
                        or if the output method is invalid.
        """
        # Retrieve all outputs from the given component
        outputs = value._outputs_map.values()
        # Prepare to collect matching output-input pairs
        matching_pairs = []
        # Get the input object from the current component
        input_ = self._inputs[input_name]
        # Iterate over outputs to find matches based on types
        matching_pairs = [
            (output, input_)
            for output in outputs
            for output_type in output.types
            # Check if the output type matches the input's accepted types
            if input_.input_types and output_type in input_.input_types
        ]
        # If multiple matches are found, raise an error indicating ambiguity
        if len(matching_pairs) > 1:
            matching_pairs_str = self._build_error_string_from_matching_pairs(matching_pairs)
            msg = self.build_component_error_message(
                f"There are multiple outputs from {value.display_name} that can connect to inputs: {matching_pairs_str}"
            )
            raise ValueError(msg)
        # If no matches are found, raise an error indicating no suitable output
        if not matching_pairs:
            msg = self.build_input_error_message(input_name, f"No matching output from {value.display_name} found")
            raise ValueError(msg)
        # Get the matching output and input pair
        output, input_ = matching_pairs[0]
        # Ensure that the output method is a valid method name (string)
        if not isinstance(output.method, str):
            msg = self.build_component_error_message(
                f"Method {output.method} is not a valid output of {value.display_name}"
            )
            raise TypeError(msg)
        return getattr(value, output.method)

    def _process_connection_or_parameter(self, key, value) -> None:
        # Special handling for Loop components: check if we're setting a loop-enabled output
        if self._is_loop_connection(key, value):
            self._process_loop_connection(key, value)
            return

        input_ = self._get_or_create_input(key)
        # We need to check if callable AND if it is a method from a class that inherits from Component
        if isinstance(value, Component):
            # We need to find the Output that can connect to an input of the current component
            # if there's more than one output that matches, we need to raise an error
            # because we don't know which one to connect to
            value = self._find_matching_output_method(key, value)
        if callable(value) and self._inherits_from_component(value):
            try:
                self._method_is_valid_output(value)
            except ValueError as e:
                msg = f"Method {value.__name__} is not a valid output of {value.__self__.__class__.__name__}"
                raise ValueError(msg) from e
            self._connect_to_component(key, value, input_)
        else:
            self._set_parameter_or_attribute(key, value)

    def _is_loop_connection(self, key: str, value) -> bool:
        """Check if this is a loop feedback connection.

        A loop connection occurs when:
        1. The key matches an output name of this component
        2. That output has allows_loop=True
        3. The value is a callable method from another component
        """
        # Check if key matches a loop-enabled output
        if key not in self._outputs_map:
            return False

        output = self._outputs_map[key]
        if not getattr(output, "allows_loop", False):
            return False

        # Check if value is a callable method from a Component
        return callable(value) and self._inherits_from_component(value)

    def _process_loop_connection(self, key: str, value) -> None:
        """Process a loop feedback connection.

        Creates a special edge that connects the source component's output
        to this Loop component's loop-enabled output (not an input).
        """
        try:
            self._method_is_valid_output(value)
        except ValueError as e:
            msg = f"Method {value.__name__} is not a valid output of {value.__self__.__class__.__name__}"
            raise ValueError(msg) from e

        source_component = value.__self__
        self._components.append(source_component)
        source_output = source_component.get_output_by_method(value)
        target_output = self._outputs_map[key]

        # Create special loop feedback edge
        self._add_loop_edge(source_component, source_output, target_output)

    def _add_loop_edge(self, source_component, source_output, target_output) -> None:
        """Add a special loop feedback edge that targets an output instead of an input."""
        self._edges.append(
            {
                "source": source_component._id,
                "target": self._id,
                "data": {
                    "sourceHandle": {
                        "dataType": source_component.name or source_component.__class__.__name__,
                        "id": source_component._id,
                        "name": source_output.name,
                        "output_types": source_output.types,
                    },
                    "targetHandle": {
                        # Special loop edge structure - targets an output, not an input
                        "dataType": self.name or self.__class__.__name__,
                        "id": self._id,
                        "name": target_output.name,
                        "output_types": target_output.types,
                    },
                },
            }
        )

    def _process_connection_or_parameters(self, key, value) -> None:
        # if value is a list of components, we need to process each component
        # Note this update make sure it is not a list str | int | float | bool | type(None)
        if isinstance(value, list) and not any(
            isinstance(val, str | int | float | bool | type(None) | Message | Data | StructuredTool) for val in value
        ):
            for val in value:
                self._process_connection_or_parameter(key, val)
        else:
            self._process_connection_or_parameter(key, value)

    def _get_or_create_input(self, key):
        try:
            return self._inputs[key]
        except KeyError:
            input_ = self._get_fallback_input(name=key, display_name=key)
            self._inputs[key] = input_
            self.inputs.append(input_)
            return input_

    def _connect_to_component(self, key, value, input_) -> None:
        component = value.__self__
        self._components.append(component)
        output = component.get_output_by_method(value)
        self._add_edge(component, key, output, input_)

    def _add_edge(self, component, key, output, input_) -> None:
        self._edges.append(
            {
                "source": component._id,
                "target": self._id,
                "data": {
                    "sourceHandle": {
                        "dataType": component.name or component.__class__.__name__,
                        "id": component._id,
                        "name": output.name,
                        "output_types": output.types,
                    },
                    "targetHandle": {
                        "fieldName": key,
                        "id": self._id,
                        "inputTypes": input_.input_types,
                        "type": input_.field_type,
                    },
                },
            }
        )

    def _set_parameter_or_attribute(self, key, value) -> None:
        if isinstance(value, Component):
            methods = ", ".join([f"'{output.method}'" for output in value.outputs])
            msg = f"You set {value.display_name} as value for `{key}`. You should pass one of the following: {methods}"
            raise TypeError(msg)
        self._set_input_value(key, value)
        self._parameters[key] = value
        self._attributes[key] = value

    def __call__(self, **kwargs):
        self.set(**kwargs)

        return run_until_complete(self.run())

    async def _run(self):
        # Resolve callable inputs
        for key, _input in self._inputs.items():
            if asyncio.iscoroutinefunction(_input.value):
                self._inputs[key].value = await _input.value()
            elif callable(_input.value):
                self._inputs[key].value = await asyncio.to_thread(_input.value)

        self.set_attributes({})

        return await self.build_results()

    def __getattr__(self, name: str) -> Any:
        if "_attributes" in self.__dict__ and name in self.__dict__["_attributes"]:
            # It is a dict of attributes that are not inputs or outputs all the raw data it should have the loop input.
            return self.__dict__["_attributes"][name]
        if "_inputs" in self.__dict__ and name in self.__dict__["_inputs"]:
            return self.__dict__["_inputs"][name].value
        if "_outputs_map" in self.__dict__ and name in self.__dict__["_outputs_map"]:
            return self.__dict__["_outputs_map"][name]
        if name in BACKWARDS_COMPATIBLE_ATTRIBUTES:
            return self.__dict__[f"_{name}"]
        if name.startswith("_") and name[1:] in BACKWARDS_COMPATIBLE_ATTRIBUTES:
            return self.__dict__[name]
        if name == "graph":
            # If it got up to here it means it was going to raise
            session_id = self._session_id if hasattr(self, "_session_id") else None
            user_id = self._user_id if hasattr(self, "_user_id") else None
            flow_name = self._flow_name if hasattr(self, "_flow_name") else None
            flow_id = self._flow_id if hasattr(self, "_flow_id") else None
            return PlaceholderGraph(
                flow_id=flow_id, user_id=str(user_id), session_id=session_id, context={}, flow_name=flow_name
            )
        msg = f"Attribute {name} not found in {self.__class__.__name__}"
        raise AttributeError(msg)

    def _set_input_value(self, name: str, value: Any) -> None:
        if name in self._inputs:
            input_value = self._inputs[name].value
            if isinstance(input_value, Component):
                methods = ", ".join([f"'{output.method}'" for output in input_value.outputs])
                msg = self.build_input_error_message(
                    name,
                    f"You set {input_value.display_name} as value. You should pass one of the following: {methods}",
                )
                raise ValueError(msg)
            if callable(input_value) and hasattr(input_value, "__self__"):
                msg = self.build_input_error_message(
                    name, f"Input is connected to {input_value.__self__.display_name}.{input_value.__name__}"
                )
                raise ValueError(msg)
            try:
                self._inputs[name].value = value
            except Exception as e:
                msg = f"Error setting input value for {name}: {e}"
                raise ValueError(msg) from e
            if hasattr(self._inputs[name], "load_from_db"):
                self._inputs[name].load_from_db = False
        else:
            msg = self.build_component_error_message(f"Input {name} not found")
            raise ValueError(msg)

    def _validate_outputs(self) -> None:
        # Raise Error if some rule isn't met
        if self.selected_output is not None and self.selected_output not in self._outputs_map:
            output_names = ", ".join(list(self._outputs_map.keys()))
            msg = f"selected_output '{self.selected_output}' is not valid. Must be one of: {output_names}"
            raise ValueError(msg)

    def _map_parameters_on_frontend_node(self, frontend_node: ComponentFrontendNode) -> None:
        for name, value in self._parameters.items():
            frontend_node.set_field_value_in_template(name, value)

    def _map_parameters_on_template(self, template: dict) -> None:
        for name, value in self._parameters.items():
            try:
                template[name]["value"] = value
            except KeyError as e:
                close_match = find_closest_match(name, list(template.keys()))
                if close_match:
                    msg = f"Parameter '{name}' not found in {self.__class__.__name__}. Did you mean '{close_match}'?"
                    raise ValueError(msg) from e
                msg = f"Parameter {name} not found in {self.__class__.__name__}. "
                raise ValueError(msg) from e

    def _get_method_return_type(self, method_name: str) -> list[str]:
        method = getattr(self, method_name)
        return_type = get_type_hints(method)["return"]
        extracted_return_types = self._extract_return_type(return_type)
        return [format_type(extracted_return_type) for extracted_return_type in extracted_return_types]

    def _update_template(self, frontend_node: dict):
        return frontend_node

    def to_frontend_node(self):
        # ! This part here is clunky but we need it like this for
        # ! backwards compatibility. We can change how prompt component
        # ! works and then update this later
        field_config = self.get_template_config(self)
        frontend_node = ComponentFrontendNode.from_inputs(**field_config)
        # for key in self._inputs:
        #     frontend_node.set_field_load_from_db_in_template(key, value=False)
        self._map_parameters_on_frontend_node(frontend_node)

        frontend_node_dict = frontend_node.to_dict(keep_name=False)
        frontend_node_dict = self._update_template(frontend_node_dict)
        self._map_parameters_on_template(frontend_node_dict["template"])

        frontend_node = ComponentFrontendNode.from_dict(frontend_node_dict)
        if not self._code:
            self.set_class_code()
        code_field = Input(
            dynamic=True,
            required=True,
            placeholder="",
            multiline=True,
            value=self._code,
            password=False,
            name="code",
            advanced=True,
            field_type="code",
            is_list=False,
        )
        frontend_node.template.add_field(code_field)

        for output in frontend_node.outputs:
            if output.types:
                continue
            return_types = self._get_method_return_type(output.method)
            output.add_types(return_types)

        frontend_node.validate_component()
        frontend_node.set_base_classes_from_outputs()

        # Get the node dictionary and add selected_output if specified
        node_dict = frontend_node.to_dict(keep_name=False)
        if self.selected_output is not None:
            node_dict["selected_output"] = self.selected_output

        return {
            "data": {
                "node": node_dict,
                "type": self.name or self.__class__.__name__,
                "id": self._id,
            },
            "id": self._id,
        }

    def _validate_inputs(self, params: dict) -> None:
        # Params keys are the `name` attribute of the Input objects
        """Validates and assigns input values from the provided parameters dictionary.

        For each parameter matching a defined input, sets the input's value and updates the parameter
        dictionary with the validated value.
        """
        for key, value in params.copy().items():
            if key not in self._inputs:
                continue
            input_ = self._inputs[key]
            # BaseInputMixin has a `validate_assignment=True`

            input_.value = value
            params[input_.name] = input_.value

    def set_attributes(self, params: dict) -> None:
        """Sets component attributes from the given parameters, preventing conflicts with reserved attribute names.

        Raises:
            ValueError: If a parameter name matches a reserved attribute not managed in _attributes and its
            value differs from the current attribute value.
        """
        self._validate_inputs(params)
        attributes = {}
        for key, value in params.items():
            if key in self.__dict__ and key not in self._attributes and value != getattr(self, key):
                msg = (
                    f"{self.__class__.__name__} defines an input parameter named '{key}' "
                    f"that is a reserved word and cannot be used."
                )
                raise ValueError(msg)
            attributes[key] = value
        for key, input_obj in self._inputs.items():
            if key not in attributes and key not in self._attributes:
                attributes[key] = input_obj.value or None

        self._attributes.update(attributes)

    def _set_outputs(self, outputs: list[dict]) -> None:
        self.outputs = [Output(**output) for output in outputs]
        for output in self.outputs:
            setattr(self, output.name, output)
            self._outputs_map[output.name] = output

    def get_trace_as_inputs(self):
        predefined_inputs = {
            input_.name: input_.value
            for input_ in self.inputs
            if hasattr(input_, "trace_as_input") and input_.trace_as_input
        }
        # Runtime inputs
        runtime_inputs = {name: input_.value for name, input_ in self._inputs.items() if hasattr(input_, "value")}
        return {**predefined_inputs, **runtime_inputs}

    def get_trace_as_metadata(self):
        return {
            input_.name: input_.value
            for input_ in self.inputs
            if hasattr(input_, "trace_as_metadata") and input_.trace_as_metadata
        }

    async def _build_with_tracing(self):
        inputs = self.get_trace_as_inputs()
        metadata = self.get_trace_as_metadata()
        async with self._tracing_service.trace_component(self, self.trace_name, inputs, metadata):
            results, artifacts = await self._build_results()
            self._tracing_service.set_outputs(self.trace_name, results)

        return results, artifacts

    async def _build_without_tracing(self):
        return await self._build_results()

    async def build_results(self):
        """Build the results of the component."""
        if hasattr(self, "graph"):
            session_id = self.graph.session_id
        elif hasattr(self, "_session_id"):
            session_id = self._session_id
        else:
            session_id = None
        try:
            if self._tracing_service:
                return await self._build_with_tracing()
            return await self._build_without_tracing()
        except StreamingError as e:
            await self.send_error(
                exception=e.cause,
                session_id=session_id,
                trace_name=getattr(self, "trace_name", None),
                source=e.source,
            )
            raise e.cause  # noqa: B904
        except Exception as e:
            await self.send_error(
                exception=e,
                session_id=session_id,
                source=Source(id=self._id, display_name=self.display_name, source=self.display_name),
                trace_name=getattr(self, "trace_name", None),
            )
            raise

    async def _build_results(self) -> tuple[dict, dict]:
        results, artifacts = {}, {}

        self._pre_run_setup_if_needed()
        self._handle_tool_mode()

        for output in self._get_outputs_to_process():
            self._current_output = output.name
            result = await self._get_output_result(output)
            results[output.name] = result
            artifacts[output.name] = self._build_artifact(result)
            self._log_output(output)

        self._finalize_results(results, artifacts)
        return results, artifacts

    def _pre_run_setup_if_needed(self):
        if hasattr(self, "_pre_run_setup"):
            self._pre_run_setup()

    def _handle_tool_mode(self):
        if (
            hasattr(self, "outputs") and any(getattr(_input, "tool_mode", False) for _input in self.inputs)
        ) or self.add_tool_output:
            self._append_tool_to_outputs_map()

    def _should_process_output(self, output):
        """Determines whether a given output should be processed based on vertex edge configuration.

        Returns True if the component has no vertex or outgoing edges, or if the output's name is among
        the vertex's source edge names.
        """
        if not self._vertex or not self._vertex.outgoing_edges:
            return True
        return output.name in self._vertex.edges_source_names

    def _get_outputs_to_process(self):
        """Returns a list of outputs to process, ordered according to self.outputs.

        Outputs are included only if they should be processed, as determined by _should_process_output.
        First processes outputs in the order defined by self.outputs, then processes any remaining outputs
        from _outputs_map that weren't in self.outputs.

        Returns:
            list: Outputs to be processed in the defined order.

        Raises:
            ValueError: If an output name in self.outputs is not present in _outputs_map.
        """
        result = []
        processed_names = set()

        # First process outputs in the order defined by self.outputs
        for output in self.outputs:
            output_obj = self._outputs_map.get(output.name, deepcopy(output))
            if self._should_process_output(output_obj):
                result.append(output_obj)
                processed_names.add(output_obj.name)

        # Then process any remaining outputs from _outputs_map
        for name, output_obj in self._outputs_map.items():
            if name not in processed_names and self._should_process_output(output_obj):
                result.append(output_obj)

        return result

    async def _get_output_result(self, output):
        """Computes and returns the result for a given output, applying caching and output options.

        If the output is cached and a value is already defined, returns the cached value. Otherwise,
        invokes the associated output method asynchronously, applies output options, updates the cache,
        and returns the result. Raises a ValueError if the output method is not defined, or a TypeError
        if the method invocation fails.
        """
        if output.cache and output.value != UNDEFINED:
            return output.value

        if output.method is None:
            msg = f'Output "{output.name}" does not have a method defined.'
            raise ValueError(msg)

        method = getattr(self, output.method)
        try:
            result = await method() if inspect.iscoroutinefunction(method) else await asyncio.to_thread(method)
        except TypeError as e:
            msg = f'Error running method "{output.method}": {e}'
            raise TypeError(msg) from e

        if (
            self._vertex is not None
            and isinstance(result, Message)
            and result.flow_id is None
            and self._vertex.graph.flow_id is not None
        ):
            result.set_flow_id(self._vertex.graph.flow_id)
        result = output.apply_options(result)
        output.value = result

        return result

    async def resolve_output(self, output_name: str) -> Any:
        """Resolves and returns the value for a specified output by name.

        If output caching is enabled and a value is already available, returns the cached value;
        otherwise, computes and returns the output result. Raises a KeyError if the output name
        does not exist.
        """
        output = self._outputs_map.get(output_name)
        if output is None:
            msg = (
                f"Sorry, an output named '{output_name}' could not be found. "
                "Please ensure that the output is correctly configured and try again."
            )
            raise KeyError(msg)
        if output.cache and output.value != UNDEFINED:
            return output.value
        return await self._get_output_result(output)

    def _build_artifact(self, result):
        """Builds an artifact dictionary containing a string representation, raw data, and type for a result.

        The artifact includes a human-readable representation, the processed raw result, and its determined type.
        """
        custom_repr = self.custom_repr()
        if custom_repr is None and isinstance(result, dict | Data | str):
            custom_repr = result
        if not isinstance(custom_repr, str):
            custom_repr = str(custom_repr)

        raw = self._process_raw_result(result)
        artifact_type = get_artifact_type(self.status or raw, result)
        raw, artifact_type = post_process_raw(raw, artifact_type)
        return {"repr": custom_repr, "raw": raw, "type": artifact_type}

    def _process_raw_result(self, result):
        return self.extract_data(result)

    def extract_data(self, result):
        """Extract the data from the result. this is where the self.status is set."""
        if isinstance(result, Message):
            self.status = result.get_text()
            return (
                self.status if self.status is not None else "No text available"
            )  # Provide a default message if .text_key is missing
        if hasattr(result, "data"):
            return result.data
        if hasattr(result, "model_dump"):
            return result.model_dump()
        if isinstance(result, Data | dict | str):
            return result.data if isinstance(result, Data) else result

        if self.status:
            return self.status
        return result

    def _log_output(self, output):
        self._output_logs[output.name] = self._logs
        self._logs = []
        self._current_output = ""

    def _finalize_results(self, results, artifacts):
        self._artifacts = artifacts
        self._results = results
        if self._tracing_service:
            self._tracing_service.set_outputs(self.trace_name, results)

    def custom_repr(self):
        if self.repr_value == "":
            self.repr_value = self.status
        if isinstance(self.repr_value, dict):
            return yaml.dump(self.repr_value)
        if isinstance(self.repr_value, str):
            return self.repr_value
        if isinstance(self.repr_value, BaseModel) and not isinstance(self.repr_value, Data):
            return str(self.repr_value)
        return self.repr_value

    def build_inputs(self):
        """Builds the inputs for the custom component.

        Returns:
            List[Input]: The list of inputs.
        """
        # This function is similar to build_config, but it will process the inputs
        # and return them as a dict with keys being the Input.name and values being the Input.model_dump()
        self.inputs = self.template_config.get("inputs", [])
        if not self.inputs:
            return {}
        return {_input.name: _input.model_dump(by_alias=True, exclude_none=True) for _input in self.inputs}

    def _get_field_order(self):
        try:
            inputs = self.template_config["inputs"]
            return [field.name for field in inputs]
        except KeyError:
            return []

    def build(self, **kwargs) -> None:
        self.set_attributes(kwargs)

    def _get_fallback_input(self, **kwargs):
        return Input(**kwargs)

    async def to_toolkit(self) -> list[Tool]:
        """Convert component to a list of tools.

        This is a template method that defines the skeleton of the toolkit creation
        algorithm. Subclasses can override _get_tools() to provide custom tool
        implementations while maintaining the metadata update functionality.

        Returns:
            list[Tool]: A list of tools with updated metadata. Each tool contains:
                - name: The name of the tool
                - description: A description of what the tool does
                - tags: List of tags associated with the tool
        """
        # Get tools from subclass implementation
        tools = await self._get_tools()

        if hasattr(self, TOOLS_METADATA_INPUT_NAME):
            tools = self._filter_tools_by_status(tools=tools, metadata=self.tools_metadata)
            return self._update_tools_with_metadata(tools=tools, metadata=self.tools_metadata)

        # If no metadata exists yet, filter based on enabled_tools
        return self._filter_tools_by_status(tools=tools, metadata=None)

    async def _get_tools(self) -> list[Tool]:
        """Get the list of tools for this component.

        This method can be overridden by subclasses to provide custom tool implementations.
        The default implementation uses ComponentToolkit.

        Returns:
            list[Tool]: List of tools provided by this component
        """
        component_toolkit: type[ComponentToolkit] = _get_component_toolkit()
        return component_toolkit(component=self).get_tools(callbacks=self.get_langchain_callbacks())

    def _extract_tools_tags(self, tools_metadata: list[dict]) -> list[str]:
        """Extract the first tag from each tool's metadata."""
        return [tool["tags"][0] for tool in tools_metadata if tool["tags"]]

    def _update_tools_with_metadata(self, tools: list[Tool], metadata: DataFrame | None) -> list[Tool]:
        """Update tools with provided metadata."""
        component_toolkit: type[ComponentToolkit] = _get_component_toolkit()
        return component_toolkit(component=self, metadata=metadata).update_tools_metadata(tools=tools)

    def check_for_tool_tag_change(self, old_tags: list[str], new_tags: list[str]) -> bool:
        # First check length - if different lengths, they can't be equal
        if len(old_tags) != len(new_tags):
            return True
        # Use set comparison for O(n) average case complexity, earlier the old_tags.sort() != new_tags.sort() was used
        return set(old_tags) != set(new_tags)

    def _filter_tools_by_status(self, tools: list[Tool], metadata: pd.DataFrame | None) -> list[Tool]:
        """Filter tools based on their status in metadata.

        Args:
            tools (list[Tool]): List of tools to filter.
            metadata (list[dict] | None): Tools metadata containing status information.

        Returns:
            list[Tool]: Filtered list of tools.
        """
        # Convert metadata to a list of dicts if it's a DataFrame
        metadata_dict = None  # Initialize as None to avoid lint issues with empty dict
        if isinstance(metadata, pd.DataFrame):
            metadata_dict = metadata.to_dict(orient="records")

        # If metadata is None or empty, use enabled_tools
        if not metadata_dict:
            enabled = self.enabled_tools
            return (
                tools
                if enabled is None
                else [
                    tool for tool in tools if any(enabled_name in [tool.name, *tool.tags] for enabled_name in enabled)
                ]
            )

        # Ensure metadata is a list of dicts
        if not isinstance(metadata_dict, list):
            return tools

        # Create a mapping of tool names to their status
        tool_status = {item["name"]: item.get("status", True) for item in metadata_dict}
        return [tool for tool in tools if tool_status.get(tool.name, True)]

    def _build_tool_data(self, tool: Tool) -> dict:
        if tool.metadata is None:
            tool.metadata = {}
        return {
            "name": tool.name,
            "description": tool.description,
            "tags": tool.tags if hasattr(tool, "tags") and tool.tags else [tool.name],
            "status": True,  # Initialize all tools with status True
            "display_name": tool.metadata.get("display_name", tool.name),
            "display_description": tool.metadata.get("display_description", tool.description),
            "readonly": tool.metadata.get("readonly", False),
            "args": tool.args,
            # "args_schema": tool.args_schema,
        }

    async def _build_tools_metadata_input(self):
        try:
            from langflow.io import ToolsInput
        except ImportError as e:
            msg = "Failed to import ToolsInput from langflow.io"
            raise ImportError(msg) from e
        placeholder = None
        tools = []
        try:
            tools = await self._get_tools()
            placeholder = "Loading actions..." if len(tools) == 0 else ""
        except (TimeoutError, asyncio.TimeoutError):
            placeholder = "Timeout loading actions"
        except (ConnectionError, OSError, ValueError):
            placeholder = "Error loading actions"
        # Always use the latest tool data
        tool_data = [self._build_tool_data(tool) for tool in tools]
        # print(tool_data)
        if hasattr(self, TOOLS_METADATA_INPUT_NAME):
            old_tags = self._extract_tools_tags(self.tools_metadata)
            new_tags = self._extract_tools_tags(tool_data)
            if self.check_for_tool_tag_change(old_tags, new_tags):
                # If enabled tools are set, update status based on them
                enabled = self.enabled_tools
                if enabled is not None:
                    for item in tool_data:
                        item["status"] = any(enabled_name in [item["name"], *item["tags"]] for enabled_name in enabled)
                self.tools_metadata = tool_data
            else:
                # Preserve existing status values
                existing_status = {item["name"]: item.get("status", True) for item in self.tools_metadata}
                for item in tool_data:
                    item["status"] = existing_status.get(item["name"], True)
                tool_data = self.tools_metadata
        else:
            # If enabled tools are set, update status based on them
            enabled = self.enabled_tools
            if enabled is not None:
                for item in tool_data:
                    item["status"] = any(enabled_name in [item["name"], *item["tags"]] for enabled_name in enabled)
            self.tools_metadata = tool_data

        return ToolsInput(
            name=TOOLS_METADATA_INPUT_NAME,
            placeholder=placeholder,
            display_name="Actions",
            info=TOOLS_METADATA_INFO,
            value=tool_data,
        )

    def get_project_name(self):
        if hasattr(self, "_tracing_service") and self._tracing_service:
            return self._tracing_service.project_name
        return "Langflow"

    def log(self, message: LoggableType | list[LoggableType], name: str | None = None) -> None:
        """Logs a message.

        Args:
            message (LoggableType | list[LoggableType]): The message to log.
            name (str, optional): The name of the log. Defaults to None.
        """
        if name is None:
            name = f"Log {len(self._logs) + 1}"
        log = Log(message=message, type=get_artifact_type(message), name=name)
        self._logs.append(log)
        if self._tracing_service and self._vertex:
            self._tracing_service.add_log(trace_name=self.trace_name, log=log)
        if self._event_manager is not None and self._current_output:
            data = log.model_dump()
            data["output"] = self._current_output
            data["component_id"] = self._id
            self._event_manager.on_log(data=data)

    def _append_tool_output(self) -> None:
        if next((output for output in self.outputs if output.name == TOOL_OUTPUT_NAME), None) is None:
            self.outputs.append(
                Output(
                    name=TOOL_OUTPUT_NAME,
                    display_name=TOOL_OUTPUT_DISPLAY_NAME,
                    method="to_toolkit",
                    types=["Tool"],
                )
            )

    def is_connected_to_chat_output(self) -> bool:
        return has_chat_output(self.graph.get_vertex_neighbors(self._vertex))

    def _is_database_available(self) -> bool:
        """Check if the database is available."""
        return get_db_service().database_available

    def _should_skip_message(self, message: Message) -> bool:
        """Check if the message should be skipped based on vertex configuration and message type."""
        return (
            self._vertex is not None
            and not (self._vertex.is_output or self._vertex.is_input)
            and not self.is_connected_to_chat_output()
            and not isinstance(message, ErrorMessage)
        ) or not self._is_database_available()

    async def send_message(self, message: Message, id_: str | None = None):
        if self._should_skip_message(message):
            return message
        if (hasattr(self, "graph") and self.graph.session_id) and (message is not None and not message.session_id):
            session_id = (
                UUID(self.graph.session_id) if isinstance(self.graph.session_id, str) else self.graph.session_id
            )
            message.session_id = session_id
        if hasattr(message, "flow_id") and isinstance(message.flow_id, str):
            message.flow_id = UUID(message.flow_id)
        stored_message = await self._store_message(message)

        self._stored_message_id = stored_message.id
        try:
            complete_message = ""
            if (
                self._should_stream_message(stored_message, message)
                and message is not None
                and isinstance(message.text, AsyncIterator | Iterator)
            ):
                complete_message = await self._stream_message(message.text, stored_message)
                stored_message.text = complete_message
                stored_message = await self._update_stored_message(stored_message)
            else:
                # Only send message event for non-streaming messages
                await self._send_message_event(stored_message, id_=id_)
        except Exception:
            # remove the message from the database
            await delete_message(stored_message.id)
            raise
        self.status = stored_message
        return stored_message

    async def _store_message(self, message: Message) -> Message:
        flow_id: str | None = None
        if hasattr(self, "graph"):
            # Convert UUID to str if needed
            flow_id = str(self.graph.flow_id) if self.graph.flow_id else None
        stored_messages = await astore_message(message, flow_id=flow_id)
        if len(stored_messages) != 1:
            msg = "Only one message can be stored at a time."
            raise ValueError(msg)
        stored_message = stored_messages[0]
        return await Message.create(**stored_message.model_dump())

    async def _send_message_event(self, message: Message, id_: str | None = None, category: str | None = None) -> None:
        if hasattr(self, "_event_manager") and self._event_manager:
            data_dict = message.model_dump()["data"] if hasattr(message, "data") else message.model_dump()
            if id_ and not data_dict.get("id"):
                data_dict["id"] = id_
            category = category or data_dict.get("category", None)

            def _send_event():
                match category:
                    case "error":
                        self._event_manager.on_error(data=data_dict)
                    case "remove_message":
                        # Check if id exists in data_dict before accessing it
                        if "id" in data_dict:
                            self._event_manager.on_remove_message(data={"id": data_dict["id"]})
                        else:
                            # If no id, try to get it from the message object or id_ parameter
                            message_id = getattr(message, "id", None) or id_
                            if message_id:
                                self._event_manager.on_remove_message(data={"id": message_id})
                    case _:
                        self._event_manager.on_message(data=data_dict)

            await asyncio.to_thread(_send_event)

    def _should_stream_message(self, stored_message: Message, original_message: Message) -> bool:
        return bool(
            hasattr(self, "_event_manager")
            and self._event_manager
            and stored_message.id
            and not isinstance(original_message.text, str)
        )

    async def _update_stored_message(self, message: Message) -> Message:
        """Update the stored message."""
        if hasattr(self, "_vertex") and self._vertex is not None and hasattr(self._vertex, "graph"):
            flow_id = (
                UUID(self._vertex.graph.flow_id)
                if isinstance(self._vertex.graph.flow_id, str)
                else self._vertex.graph.flow_id
            )

            message.flow_id = flow_id

        message_tables = await aupdate_messages(message)
        if not message_tables:
            msg = "Failed to update message"
            raise ValueError(msg)
        message_table = message_tables[0]
        return await Message.create(**message_table.model_dump())

    async def _stream_message(self, iterator: AsyncIterator | Iterator, message: Message) -> str:
        if not isinstance(iterator, AsyncIterator | Iterator):
            msg = "The message must be an iterator or an async iterator."
            raise TypeError(msg)

        if isinstance(iterator, AsyncIterator):
            return await self._handle_async_iterator(iterator, message.id, message)
        try:
            complete_message = ""
            first_chunk = True
            for chunk in iterator:
                complete_message = await self._process_chunk(
                    chunk.content, complete_message, message.id, message, first_chunk=first_chunk
                )
                first_chunk = False
        except Exception as e:
            raise StreamingError(cause=e, source=message.properties.source) from e
        else:
            return complete_message

    async def _handle_async_iterator(self, iterator: AsyncIterator, message_id: str, message: Message) -> str:
        complete_message = ""
        first_chunk = True
        async for chunk in iterator:
            complete_message = await self._process_chunk(
                chunk.content, complete_message, message_id, message, first_chunk=first_chunk
            )
            first_chunk = False
        return complete_message

    async def _process_chunk(
        self, chunk: str, complete_message: str, message_id: str, message: Message, *, first_chunk: bool = False
    ) -> str:
        complete_message += chunk
        if self._event_manager:
            if first_chunk:
                # Send the initial message only on the first chunk
                msg_copy = message.model_copy()
                msg_copy.text = complete_message
                await self._send_message_event(msg_copy, id_=message_id)
            await asyncio.to_thread(
                self._event_manager.on_token,
                data={
                    "chunk": chunk,
                    "id": str(message_id),
                },
            )
        return complete_message

    async def send_error(
        self,
        exception: Exception,
        session_id: str,
        trace_name: str,
        source: Source,
    ) -> Message | None:
        """Send an error message to the frontend."""
        flow_id = self.graph.flow_id if hasattr(self, "graph") else None
        if not session_id:
            return None
        error_message = ErrorMessage(
            flow_id=flow_id,
            exception=exception,
            session_id=session_id,
            trace_name=trace_name,
            source=source,
        )
        await self.send_message(error_message)
        return error_message

    def _append_tool_to_outputs_map(self):
        self._outputs_map[TOOL_OUTPUT_NAME] = self._build_tool_output()
        # add a new input for the tool schema
        # self.inputs.append(self._build_tool_schema())

    def _build_tool_output(self) -> Output:
        return Output(name=TOOL_OUTPUT_NAME, display_name=TOOL_OUTPUT_DISPLAY_NAME, method="to_toolkit", types=["Tool"])

    def get_input_display_name(self, input_name: str) -> str:
        """Get the display name of an input.

        This is a public utility method that subclasses can use to get user-friendly
        display names for inputs when building error messages or UI elements.

        Usage:
            msg = f"Input {self.get_input_display_name(input_name)} not found"

        Args:
            input_name (str): The name of the input.

        Returns:
            str: The display name of the input, or the input name if not found.
        """
        if input_name in self._inputs:
            return getattr(self._inputs[input_name], "display_name", input_name)
        return input_name

    def get_output_display_name(self, output_name: str) -> str:
        """Get the display name of an output.

        This is a public utility method that subclasses can use to get user-friendly
        display names for outputs when building error messages or UI elements.

        Args:
            output_name (str): The name of the output.

        Returns:
            str: The display name of the output, or the output name if not found.
        """
        if output_name in self._outputs_map:
            return getattr(self._outputs_map[output_name], "display_name", output_name)
        return output_name

    def build_input_error_message(self, input_name: str, message: str) -> str:
        """Build an error message for an input.

        This is a public utility method that subclasses can use to create consistent,
        user-friendly error messages that reference inputs by their display names.
        The input name is placed at the beginning to ensure it's visible even if the message is truncated.

        Args:
            input_name (str): The name of the input.
            message (str): The error message.

        Returns:
            str: The formatted error message with display name.
        """
        display_name = self.get_input_display_name(input_name)
        return f"[Input: {display_name}] {message}"

    def build_output_error_message(self, output_name: str, message: str) -> str:
        """Build an error message for an output.

        This is a public utility method that subclasses can use to create consistent,
        user-friendly error messages that reference outputs by their display names.
        The output name is placed at the beginning to ensure it's visible even if the message is truncated.

        Args:
            output_name (str): The name of the output.
            message (str): The error message.

        Returns:
            str: The formatted error message with display name.
        """
        display_name = self.get_output_display_name(output_name)
        return f"[Output: {display_name}] {message}"

    def build_component_error_message(self, message: str) -> str:
        """Build an error message for the component.

        This is a public utility method that subclasses can use to create consistent,
        user-friendly error messages that reference the component by its display name.
        The component name is placed at the beginning to ensure it's visible even if the message is truncated.

        Args:
            message (str): The error message.

        Returns:
            str: The formatted error message with component display name.
        """
        return f"[Component: {self.display_name or self.__class__.__name__}] {message}"
