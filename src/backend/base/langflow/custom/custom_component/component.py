import inspect
from typing import Any, Callable, ClassVar, List, Optional, Union
from uuid import UUID

import yaml
from pydantic import BaseModel

from langflow.inputs.inputs import InputTypes
from langflow.schema.artifact import get_artifact_type, post_process_raw
from langflow.schema.data import Data
from langflow.schema.message import Message
from langflow.services.tracing.schema import Log
from langflow.template.field.base import UNDEFINED, Output

from .custom_component import CustomComponent


class Component(CustomComponent):
    inputs: List[InputTypes] = []
    outputs: List[Output] = []
    code_class_base_inheritance: ClassVar[str] = "Component"
    _output_logs: dict[str, Log] = {}

    def __init__(self, **data):
        self._inputs: dict[str, InputTypes] = {}
        self._results: dict[str, Any] = {}
        self._attributes: dict[str, Any] = {}
        self._parameters: dict[str, Any] = {}
        self._output_logs = {}
        super().__init__(**data)
        if not hasattr(self, "trace_type"):
            self.trace_type = "chain"
        if self.inputs is not None:
            self.map_inputs(self.inputs)
        self.set_attributes(self._parameters)

    def __getattr__(self, name: str) -> Any:
        if "_attributes" in self.__dict__ and name in self.__dict__["_attributes"]:
            return self.__dict__["_attributes"][name]
        if "_inputs" in self.__dict__ and name in self.__dict__["_inputs"]:
            return self.__dict__["_inputs"][name].value
        raise AttributeError(f"{name} not found in {self.__class__.__name__}")

    def map_inputs(self, inputs: List[InputTypes]):
        self.inputs = inputs
        for input_ in inputs:
            if input_.name is None:
                raise ValueError("Input name cannot be None.")
            self._inputs[input_.name] = input_

    def validate(self, params: dict):
        self._validate_inputs(params)
        self._validate_outputs()

    def _validate_outputs(self):
        # Raise Error if some rule isn't met
        pass

    def _validate_inputs(self, params: dict):
        # Params keys are the `name` attribute of the Input objects
        for key, value in params.copy().items():
            if key not in self._inputs:
                continue
            input_ = self._inputs[key]
            # BaseInputMixin has a `validate_assignment=True`
            input_.value = value
            params[input_.name] = input_.value

    def set_attributes(self, params: dict):
        self._validate_inputs(params)
        _attributes = {}
        for key, value in params.items():
            if key in self.__dict__:
                raise ValueError(
                    f"{self.__class__.__name__} defines an input parameter named '{key}' "
                    f"that is a reserved word and cannot be used."
                )
            _attributes[key] = value
        for key, input_obj in self._inputs.items():
            if key not in _attributes:
                _attributes[key] = input_obj.value or None
        self._attributes = _attributes

    def _set_outputs(self, outputs: List[dict]):
        self.outputs = [Output(**output) for output in outputs]
        for output in self.outputs:
            setattr(self, output.name, output)

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
        async with self.tracing_service.trace_context(self, self.trace_name, inputs, metadata):
            _results, _artifacts = await self._build_results()
            self.tracing_service.set_outputs(self.trace_name, _results)

        return _results, _artifacts

    async def _build_without_tracing(self):
        return await self._build_results()

    async def build_results(self):
        if self.tracing_service:
            return await self._build_with_tracing()
        return await self._build_without_tracing()

    async def _build_results(self):
        _results = {}
        _artifacts = {}
        if hasattr(self, "outputs"):
            self._set_outputs(self.vertex.outputs)
            for output in self.outputs:
                # Build the output if it's connected to some other vertex
                # or if it's not connected to any vertex
                if not self.vertex.outgoing_edges or output.name in self.vertex.edges_source_names:
                    if output.method is None:
                        raise ValueError(f"Output {output.name} does not have a method defined.")
                    method: Callable = getattr(self, output.method)
                    if output.cache and output.value != UNDEFINED:
                        _results[output.name] = output.value
                    else:
                        result = method()
                        # If the method is asynchronous, we need to await it
                        if inspect.iscoroutinefunction(method):
                            result = await result
                        if (
                            isinstance(result, Message)
                            and result.flow_id is None
                            and self.vertex.graph.flow_id is not None
                        ):
                            result.set_flow_id(self.vertex.graph.flow_id)
                        _results[output.name] = result
                        output.value = result
                        custom_repr = self.custom_repr()
                        if custom_repr is None and isinstance(result, (dict, Data, str)):
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
                        if raw is None and isinstance(result, (dict, Data, str)):
                            raw = result.data if isinstance(result, Data) else result
                        artifact_type = get_artifact_type(artifact_value, result)
                        raw, artifact_type = post_process_raw(raw, artifact_type)
                        artifact = {"repr": custom_repr, "raw": raw, "type": artifact_type}
                        _artifacts[output.name] = artifact
                        self._output_logs[output.name] = self._logs
                        self._logs = []
        self._artifacts = _artifacts
        self._results = _results
        if self.tracing_service:
            self.tracing_service.set_outputs(self.trace_name, _results)
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

    def build_inputs(self, user_id: Optional[Union[str, UUID]] = None):
        """
        Builds the inputs for the custom component.

        Args:
            user_id (Optional[Union[str, UUID]], optional): The user ID. Defaults to None.

        Returns:
            List[Input]: The list of inputs.
        """
        # This function is similar to build_config, but it will process the inputs
        # and return them as a dict with keys being the Input.name and values being the Input.model_dump()
        self.inputs = self.template_config.get("inputs", [])
        if not self.inputs:
            return {}
        build_config = {_input.name: _input.model_dump(by_alias=True, exclude_none=True) for _input in self.inputs}
        return build_config

    def _get_field_order(self):
        try:
            inputs = self.template_config["inputs"]
            return [field.name for field in inputs]
        except KeyError:
            return []

    def build(self, **kwargs):
        self.set_attributes(kwargs)
