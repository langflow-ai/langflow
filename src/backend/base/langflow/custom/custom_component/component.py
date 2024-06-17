import inspect
from typing import AsyncIterator, Awaitable, Callable, ClassVar, Generator, Iterator, List, Optional, Union
from uuid import UUID

import yaml
from git import TYPE_CHECKING
from pydantic import BaseModel

from langflow.inputs.inputs import InputTypes
from langflow.schema.artifact import get_artifact_type, post_process_raw
from langflow.schema.data import Data
from langflow.schema.message import Message
from langflow.template.field.base import UNDEFINED, Input, Output

from .custom_component import CustomComponent

if TYPE_CHECKING:
    from langflow.graph.vertex.base import Vertex


def recursive_serialize_or_str(obj):
    try:
        if isinstance(obj, dict):
            return {k: recursive_serialize_or_str(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [recursive_serialize_or_str(v) for v in obj]
        elif isinstance(obj, BaseModel):
            return {k: recursive_serialize_or_str(v) for k, v in obj.model_dump().items()}
        elif isinstance(obj, (AsyncIterator, Generator, Iterator)):
            # contain memory addresses
            # without consuming the iterator
            # return list(obj) consumes the iterator
            # return f"{obj}" this generates '<generator object BaseChatModel.stream at 0x33e9ec770>'
            # it is not useful
            return "Unconsumed Stream"
        return str(obj)
    except Exception:
        return str(obj)


class Component(CustomComponent):
    inputs: Optional[List[InputTypes]] = None
    outputs: Optional[List[Output]] = None
    code_class_base_inheritance: ClassVar[str] = "Component"
    _results: dict = {}
    _arguments: dict = {}
    _inputs: dict[str, InputTypes] = {}

    def __init__(self, **data):
        super().__init__(**data)
        if self.inputs is not None:
            self.map_inputs(self.inputs)

    def map_inputs(self, inputs: List[Input]):
        self._inputs = {}
        self.inputs = inputs
        for input_ in inputs:
            self._inputs[input_.name] = input_

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
        for key, value in params.items():
            if key in self.__dict__:
                raise ValueError(f"Key {key} already exists in {self.__class__.__name__}")
            setattr(self, key, value)
        self._arguments = params

    def _set_outputs(self, outputs: List[dict]):
        self.outputs = [Output(**output) for output in outputs]
        for output in self.outputs:
            setattr(self, output.name, output)

    async def build_results(self, vertex: "Vertex"):
        _results = {}
        _artifacts = {}
        if hasattr(self, "outputs"):
            self._set_outputs(vertex.outputs)
            for output in self.outputs:
                # Build the output if it's connected to some other vertex
                # or if it's not connected to any vertex
                if not vertex.outgoing_edges or output.name in vertex.edges_source_names:
                    method: Callable | Awaitable = getattr(self, output.method)
                    if output.cache and output.value != UNDEFINED:
                        _results[output.name] = output.value
                    else:
                        result = method()
                        # If the method is asynchronous, we need to await it
                        if inspect.iscoroutinefunction(method):
                            result = await result
                        if isinstance(result, Message) and result.flow_id is None:
                            result.set_flow_id(vertex.graph.flow_id)
                        _results[output.name] = result
                        output.value = result
                        custom_repr = self.custom_repr()
                        if custom_repr is None and isinstance(result, (dict, Data, str)):
                            custom_repr = result
                        if not isinstance(custom_repr, str):
                            custom_repr = str(custom_repr)
                        raw = result
                        if hasattr(raw, "data") and raw is not None:
                            raw = raw.data
                        if raw is None:
                            raw = custom_repr

                        elif hasattr(raw, "model_dump") and raw is not None:
                            raw = raw.model_dump()
                        if raw is None and isinstance(result, (dict, Data, str)):
                            raw = result.data if isinstance(result, Data) else result

                        artifact_type = get_artifact_type(self.status or raw, result)
                        raw = post_process_raw(raw, artifact_type)
                        artifact = {"repr": custom_repr, "raw": raw, "type": artifact_type}
                        _artifacts[output.name] = artifact
        self._artifacts = _artifacts
        self._results = _results
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
