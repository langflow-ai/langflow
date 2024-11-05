from __future__ import annotations

import ast
import asyncio
import inspect
from collections.abc import AsyncIterator, Iterator
from copy import deepcopy
from textwrap import dedent
from typing import TYPE_CHECKING, Any, ClassVar, get_type_hints

import nanoid
import yaml
from pydantic import BaseModel, ValidationError

from langflow.base.tools.constants import TOOL_OUTPUT_NAME
from langflow.custom.tree_visitor import RequiredInputsVisitor
from langflow.exceptions.component import StreamingError
from langflow.field_typing import Tool  # noqa: TCH001 Needed by _add_toolkit_output
from langflow.graph.state.model import create_state_model
from langflow.helpers.custom import format_type
from langflow.memory import delete_message, store_message, update_messages
from langflow.schema.artifact import get_artifact_type, post_process_raw
from langflow.schema.data import Data
from langflow.schema.message import ErrorMessage, Message
from langflow.schema.properties import Source
from langflow.services.settings.feature_flags import FEATURE_FLAGS
from langflow.services.tracing.schema import Log
from langflow.template.field.base import UNDEFINED, Input, Output
from langflow.template.frontend_node.custom_components import ComponentFrontendNode
from langflow.utils.async_helpers import run_until_complete
from langflow.utils.util import find_closest_match

from .custom_component import CustomComponent

if TYPE_CHECKING:
    from collections.abc import Callable

    from langflow.events.event_manager import EventManager
    from langflow.graph.edge.schema import EdgeData
    from langflow.graph.vertex.base import Vertex
    from langflow.inputs.inputs import InputTypes
    from langflow.schema import dotdict
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


class Component(CustomComponent):
    inputs: list[InputTypes] = []
    outputs: list[Output] = []
    code_class_base_inheritance: ClassVar[str] = "Component"
    _output_logs: dict[str, list[Log]] = {}
    _current_output: str = ""
    _metadata: dict = {}

    def __init__(self, **kwargs) -> None:
        # if key starts with _ it is a config
        # else it is an input
        inputs = {}
        config = {}
        for key, value in kwargs.items():
            if key.startswith("_"):
                config[key] = value
            elif key in CONFIG_ATTRIBUTES:
                config[key[1:]] = value
            else:
                inputs[key] = value
        self._inputs: dict[str, InputTypes] = {}
        self._outputs_map: dict[str, Output] = {}
        self._results: dict[str, Any] = {}
        self._attributes: dict[str, Any] = {}
        self._parameters = inputs or {}
        self._edges: list[EdgeData] = []
        self._components: list[Component] = []
        self._current_output = ""
        self._event_manager: EventManager | None = None
        self._state_model = None
        self.set_attributes(self._parameters)
        self._output_logs = {}
        config = config or {}
        if "_id" not in config:
            config |= {"_id": f"{self.__class__.__name__}-{nanoid.generate(size=5)}"}
        self.__inputs = inputs
        self.__config = config
        self._reset_all_output_values()
        super().__init__(**config)
        if (FEATURE_FLAGS.add_toolkit_output) and hasattr(self, "_append_tool_output") and self.add_tool_output:
            self._append_tool_output()
        if hasattr(self, "_trace_type"):
            self.trace_type = self._trace_type
        if not hasattr(self, "trace_type"):
            self.trace_type = "chain"
        if self.inputs is not None:
            self.map_inputs(self.inputs)
        if self.outputs is not None:
            self.map_outputs(self.outputs)
        # Set output types
        self._set_output_types(list(self._outputs_map.values()))
        self.set_class_code()
        self._set_output_required_inputs()

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

    def __deepcopy__(self, memo):
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
        new_component._logs = self._logs
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
        except OSError as e:
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

    def map_outputs(self, outputs: list[Output]) -> None:
        """Maps the given list of outputs to the component.

        Args:
            outputs (List[Output]): The list of outputs to be mapped.

        Raises:
            ValueError: If the output name is None.

        Returns:
            None
        """
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
                msg = "Input name cannot be None."
                raise ValueError(msg)
            self._inputs[input_.name] = deepcopy(input_)

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

    def update_inputs(
        self,
        build_config: dotdict,
        field_value: Any,
        field_name: str | None = None,
    ):
        return self.update_build_config(build_config, field_value, field_name)

    def run_and_validate_update_outputs(self, frontend_node: dict, field_name: str, field_value: Any):
        frontend_node = self.update_outputs(frontend_node, field_name, field_value)
        return self._validate_frontend_node(frontend_node)

    def _validate_frontend_node(self, frontend_node: dict):
        # Check if all outputs are either Output or a valid Output model
        for index, output in enumerate(frontend_node["outputs"]):
            if isinstance(output, dict):
                try:
                    _output = Output(**output)
                    self._set_output_return_type(_output)
                    _output_dict = _output.model_dump()
                except ValidationError as e:
                    msg = f"Invalid output: {e}"
                    raise ValueError(msg) from e
            elif isinstance(output, Output):
                # we need to serialize it
                self._set_output_return_type(output)
                _output_dict = output.model_dump()
            else:
                msg = f"Invalid output type: {type(output)}"
                raise TypeError(msg)
            frontend_node["outputs"][index] = _output_dict
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
        output.set_selected()

    def _set_output_required_inputs(self) -> None:
        for output in self.outputs:
            if output.required_inputs:
                continue
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
            msg = (
                f"There are multiple outputs from {value.__class__.__name__} "
                f"that can connect to inputs in {self.__class__.__name__}: {matching_pairs_str}"
            )
        # If no matches are found, raise an error indicating no suitable output
        if not matching_pairs:
            msg = (
                f"No matching output from {value.__class__.__name__} found for input '{input_name}' "
                f"in {self.__class__.__name__}."
            )
            raise ValueError(msg)
        # Get the matching output and input pair
        output, input_ = matching_pairs[0]
        # Ensure that the output method is a valid method name (string)
        if not isinstance(output.method, str):
            msg = f"Method {output.method} is not a valid output of {value.__class__.__name__}"
            raise TypeError(msg)
        return getattr(value, output.method)

    def _process_connection_or_parameter(self, key, value) -> None:
        _input = self._get_or_create_input(key)
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
            self._connect_to_component(key, value, _input)
        else:
            self._set_parameter_or_attribute(key, value)

    def _process_connection_or_parameters(self, key, value) -> None:
        # if value is a list of components, we need to process each component
        # Note this update make sure it is not a list str | int | float | bool | type(None)
        if isinstance(value, list) and not any(
            isinstance(val, str | int | float | bool | type(None) | Message | Data) for val in value
        ):
            for val in value:
                self._process_connection_or_parameter(key, val)
        else:
            self._process_connection_or_parameter(key, value)

    def _get_or_create_input(self, key):
        try:
            return self._inputs[key]
        except KeyError:
            _input = self._get_fallback_input(name=key, display_name=key)
            self._inputs[key] = _input
            self.inputs.append(_input)
            return _input

    def _connect_to_component(self, key, value, _input) -> None:
        component = value.__self__
        self._components.append(component)
        output = component.get_output_by_method(value)
        self._add_edge(component, key, output, _input)

    def _add_edge(self, component, key, output, _input) -> None:
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
                        "inputTypes": _input.input_types,
                        "type": _input.field_type,
                    },
                },
            }
        )

    def _set_parameter_or_attribute(self, key, value) -> None:
        if isinstance(value, Component):
            methods = ", ".join([f"'{output.method}'" for output in value.outputs])
            msg = (
                f"You set {value.display_name} as value for `{key}`. "
                f"You should pass one of the following: {methods}"
            )
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
            return self.__dict__["_attributes"][name]
        if "_inputs" in self.__dict__ and name in self.__dict__["_inputs"]:
            return self.__dict__["_inputs"][name].value
        if "_outputs_map" in self.__dict__ and name in self.__dict__["_outputs_map"]:
            return self.__dict__["_outputs_map"][name]
        if name in BACKWARDS_COMPATIBLE_ATTRIBUTES:
            return self.__dict__[f"_{name}"]
        if name.startswith("_") and name[1:] in BACKWARDS_COMPATIBLE_ATTRIBUTES:
            return self.__dict__[name]
        msg = f"{name} not found in {self.__class__.__name__}"
        raise AttributeError(msg)

    def _set_input_value(self, name: str, value: Any) -> None:
        if name in self._inputs:
            input_value = self._inputs[name].value
            if isinstance(input_value, Component):
                methods = ", ".join([f"'{output.method}'" for output in input_value.outputs])
                msg = (
                    f"You set {input_value.display_name} as value for `{name}`. "
                    f"You should pass one of the following: {methods}"
                )
                raise ValueError(msg)
            if callable(input_value):
                msg = f"Input {name} is connected to {input_value.__self__.display_name}.{input_value.__name__}"
                raise ValueError(msg)
            self._inputs[name].value = value
            if hasattr(self._inputs[name], "load_from_db"):
                self._inputs[name].load_from_db = False
        else:
            msg = f"Input {name} not found in {self.__class__.__name__}"
            raise ValueError(msg)

    def _validate_outputs(self) -> None:
        # Raise Error if some rule isn't met
        pass

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
        for key in self._inputs:
            frontend_node.set_field_load_from_db_in_template(key, value=False)
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
            output.set_selected()

        frontend_node.validate_component()
        frontend_node.set_base_classes_from_outputs()
        return {
            "data": {
                "node": frontend_node.to_dict(keep_name=False),
                "type": self.name or self.__class__.__name__,
                "id": self._id,
            },
            "id": self._id,
        }

    def _validate_inputs(self, params: dict) -> None:
        # Params keys are the `name` attribute of the Input objects
        for key, value in params.copy().items():
            if key not in self._inputs:
                continue
            input_ = self._inputs[key]
            # BaseInputMixin has a `validate_assignment=True`

            input_.value = value
            params[input_.name] = input_.value

    def set_attributes(self, params: dict) -> None:
        self._validate_inputs(params)
        _attributes = {}
        for key, value in params.items():
            if key in self.__dict__ and value != getattr(self, key):
                msg = (
                    f"{self.__class__.__name__} defines an input parameter named '{key}' "
                    f"that is a reserved word and cannot be used."
                )
                raise ValueError(msg)
            _attributes[key] = value
        for key, input_obj in self._inputs.items():
            if key not in _attributes:
                _attributes[key] = input_obj.value or None
        self._attributes = _attributes

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
        # Dynamic inputs
        dynamic_inputs = {key: value for key, value in self._attributes.items() if key not in predefined_inputs}
        return {**predefined_inputs, **dynamic_inputs}

    def get_trace_as_metadata(self):
        return {
            input_.name: input_.value
            for input_ in self.inputs
            if hasattr(input_, "trace_as_metadata") and input_.trace_as_metadata
        }

    async def _build_with_tracing(self):
        inputs = self.get_trace_as_inputs()
        metadata = self.get_trace_as_metadata()
        async with self._tracing_service.trace_context(self, self.trace_name, inputs, metadata):
            _results, _artifacts = await self._build_results()
            self._tracing_service.set_outputs(self.trace_name, _results)

        return _results, _artifacts

    async def _build_without_tracing(self):
        return await self._build_results()

    async def build_results(self):
        """Build the results of the component."""
        try:
            if self._tracing_service:
                return await self._build_with_tracing()
            return await self._build_without_tracing()
        except StreamingError as e:
            self.send_error(
                exception=e.cause,
                session_id=self.graph.session_id,
                trace_name=getattr(self, "trace_name", None),
                source=e.source,
            )
            raise e.cause  # noqa: B904
        except Exception as e:
            self.send_error(
                exception=e,
                session_id=self.graph.session_id,
                source=Source(id=self._id, display_name=self.display_name, source=self.display_name),
                trace_name=getattr(self, "trace_name", None),
            )
            raise

    async def _build_results(self) -> tuple[dict, dict]:
        _results = {}
        _artifacts = {}
        if hasattr(self, "outputs"):
            for output in self._outputs_map.values():
                # Build the output if it's connected to some other vertex
                # or if it's not connected to any vertex
                if (
                    not self._vertex
                    or not self._vertex.outgoing_edges
                    or output.name in self._vertex.edges_source_names
                ):
                    if output.method is None:
                        msg = f"Output {output.name} does not have a method defined."
                        raise ValueError(msg)
                    self._current_output = output.name
                    method: Callable = getattr(self, output.method)
                    if output.cache and output.value != UNDEFINED:
                        _results[output.name] = output.value
                        result = output.value
                    else:
                        # If the method is asynchronous, we need to await it
                        if inspect.iscoroutinefunction(method):
                            result = await method()
                        else:
                            result = await asyncio.to_thread(method)
                        if (
                            self._vertex is not None
                            and isinstance(result, Message)
                            and result.flow_id is None
                            and self._vertex.graph.flow_id is not None
                        ):
                            result.set_flow_id(self._vertex.graph.flow_id)
                        _results[output.name] = result
                        output.value = result

                    custom_repr = self.custom_repr()
                    if custom_repr is None and isinstance(result, dict | Data | str):
                        custom_repr = result
                    if not isinstance(custom_repr, str):
                        custom_repr = str(custom_repr)
                    raw = result
                    if self.status is None:
                        artifact_value = raw
                    else:
                        artifact_value = self.status
                        raw = self.status

                    if hasattr(raw, "data") and raw is not None:
                        raw = raw.data
                    if raw is None:
                        raw = custom_repr

                    elif hasattr(raw, "model_dump") and raw is not None:
                        raw = raw.model_dump()
                    if raw is None and isinstance(result, dict | Data | str):
                        raw = result.data if isinstance(result, Data) else result
                    artifact_type = get_artifact_type(artifact_value, result)
                    raw, artifact_type = post_process_raw(raw, artifact_type)
                    artifact = {"repr": custom_repr, "raw": raw, "type": artifact_type}
                    _artifacts[output.name] = artifact
                    self._output_logs[output.name] = self._logs
                    self._logs = []
                    self._current_output = ""
        self._artifacts = _artifacts
        self._results = _results
        if self._tracing_service:
            self._tracing_service.set_outputs(self.trace_name, _results)
        return _results, _artifacts

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

    def to_toolkit(self) -> list[Tool]:
        component_toolkit = _get_component_toolkit()
        return component_toolkit(component=self).get_tools()

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
            self.outputs.append(Output(name=TOOL_OUTPUT_NAME, display_name="Tool", method="to_toolkit", types=["Tool"]))

    def send_message(self, message: Message, id_: str | None = None):
        if self.graph.session_id and message is not None and message.session_id is None:
            message.session_id = self.graph.session_id
        stored_message = self._store_message(message)

        self._stored_message_id = stored_message.id
        try:
            complete_message = ""
            if (
                self._should_stream_message(stored_message, message)
                and message is not None
                and isinstance(message.text, AsyncIterator | Iterator)
            ):
                complete_message = self._stream_message(message.text, stored_message)
                stored_message.text = complete_message
                stored_message = self._update_stored_message(stored_message)
            else:
                # Only send message event for non-streaming messages
                self._send_message_event(stored_message, id_=id_)
        except Exception:
            # remove the message from the database
            delete_message(stored_message.id)
            raise
        self.status = stored_message
        return stored_message

    def _store_message(self, message: Message) -> Message:
        messages = store_message(message, flow_id=self.graph.flow_id)
        if len(messages) != 1:
            msg = "Only one message can be stored at a time."
            raise ValueError(msg)

        return messages[0]

    def _send_message_event(self, message: Message, id_: str | None = None):
        if hasattr(self, "_event_manager") and self._event_manager:
            data_dict = message.data.copy() if hasattr(message, "data") else message.model_dump()
            if id_ and not data_dict.get("id"):
                data_dict["id"] = id_
            category = data_dict.get("category", None)
            match category:
                case "error":
                    self._event_manager.on_error(data=data_dict)
                case _:
                    self._event_manager.on_message(data=data_dict)

    def _should_stream_message(self, stored_message: Message, original_message: Message) -> bool:
        return bool(
            hasattr(self, "_event_manager")
            and self._event_manager
            and stored_message.id
            and not isinstance(original_message.text, str)
        )

    def _update_stored_message(self, stored_message: Message) -> Message:
        message_tables = update_messages(stored_message)
        if len(message_tables) != 1:
            msg = "Only one message can be updated at a time."
            raise ValueError(msg)
        message_table = message_tables[0]
        updated_message = Message(**message_table.model_dump())
        self.vertex._added_message = updated_message
        return updated_message

    def _stream_message(self, iterator: AsyncIterator | Iterator, message: Message) -> str:
        if not isinstance(iterator, AsyncIterator | Iterator):
            msg = "The message must be an iterator or an async iterator."
            raise TypeError(msg)

        if isinstance(iterator, AsyncIterator):
            return run_until_complete(self._handle_async_iterator(iterator, message.id, message))
        try:
            complete_message = ""
            first_chunk = True
            for chunk in iterator:
                complete_message = self._process_chunk(
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
            complete_message = self._process_chunk(
                chunk.content, complete_message, message_id, message, first_chunk=first_chunk
            )
            first_chunk = False
        return complete_message

    def _process_chunk(
        self, chunk: str, complete_message: str, message_id: str, message: Message, *, first_chunk: bool = False
    ) -> str:
        complete_message += chunk
        if self._event_manager:
            if first_chunk:
                # Send the initial message only on the first chunk
                msg_copy = message.model_copy()
                msg_copy.text = complete_message
                self._send_message_event(msg_copy, id_=message_id)
            self._event_manager.on_token(
                data={
                    "chunk": chunk,
                    "id": str(message_id),
                }
            )
        return complete_message

    def send_error(
        self,
        exception: Exception,
        session_id: str,
        trace_name: str,
        source: Source,
    ) -> None:
        """Send an error message to the frontend."""
        error_message = ErrorMessage(
            flow_id=self.graph.flow_id,
            exception=exception,
            session_id=session_id,
            trace_name=trace_name,
            source=source,
        )
        self.send_message(error_message)
