# Path: src/backend/langflow/graph/vertex/base.py
from langflow.cache import base as cache_utils
from langflow.graph.vertex.constants import DIRECT_TYPES
from langflow.interface import loading
from langflow.interface.listing import ALL_TYPES_DICT
from langflow.utils.logger import logger
from langflow.utils.util import sync_to_async
from langflow.graph.edge.contract import ContractEdge

import contextlib
import inspect
import types
import warnings
from typing import Any, Dict, List, Optional
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class Vertex:
    can_be_root: bool = False

    def __init__(self, data: Dict, base_type: Optional[str] = None) -> None:
        self.id: str = data["id"]
        self._data = data
        self.edges: List["ContractEdge"] = []
        self.base_type: Optional[str] = base_type
        self._parse_data()
        self._built_object = None
        self._built = False
        self.params = {}

    def _parse_data(self) -> None:
        self.data = self._data["data"]
        self.output = self.data["node"]["base_classes"]
        template_dicts = {
            key: value
            for key, value in self.data["node"]["template"].items()
            if isinstance(value, dict)
        }

        self.required_inputs = [
            template_dicts[key]["type"]
            for key, value in template_dicts.items()
            if value["required"]
        ]
        self.optional_inputs = [
            template_dicts[key]["type"]
            for key, value in template_dicts.items()
            if not value["required"]
        ]

        template_dict = self.data["node"]["template"]
        self.vertex_type = (
            self.data["type"]
            if "Tool" not in self.output or template_dict["_type"].islower()
            else template_dict["_type"]
        )

        if self.base_type is None:
            for base_type, value in ALL_TYPES_DICT.items():
                if self.vertex_type in value:
                    self.base_type = base_type
                    break

    def _build_params(self):
        template_dict = {
            key: value
            for key, value in self.data["node"]["template"].items()
            if isinstance(value, dict)
        }

        for key, value in template_dict.items():
            if key == "_type" or self.params.get(key) is not None:
                continue

            if value.get("type") == "file":
                self.params[key] = self._load_file_params(key, value)

            elif value.get("type") not in DIRECT_TYPES:
                edge_param = self._get_edge_params(key, value)
                if edge_param is not None:
                    self.params[key] = edge_param

            elif value["required"] or value.get("value"):
                self.params[key] = self._get_basic_params(key, value)

    def _get_basic_params(self, key: str, value: Dict) -> Any:
        new_value = value.get("value")
        if new_value is None:
            warnings.warn(f"Value for {key} in {self.vertex_type} is None. ")
        if value.get("type") == "int":
            with contextlib.suppress(TypeError, ValueError):
                new_value = int(new_value)  # type: ignore
        return new_value

    def _get_edge_params(self, key: str, value: Dict) -> Any:
        matching_edges = [
            edge
            for edge in self.edges
            if edge.target == self and edge.matched_type in value["type"]
        ]

        if value["required"] and not matching_edges:
            raise ValueError(
                f"Required input {key} for module {self.vertex_type} not found. Current inputs: {self.params}"
            )
        elif value["list"]:
            return matching_edges
        elif matching_edges:
            return matching_edges[0]
        else:
            return None

    def _load_file_params(self, key: str, value: Dict) -> str:
        file_name = value.get("value")
        content = value.get("content")
        type_to_load = value.get("suffixes")
        return cache_utils.save_binary_file(  # type: ignore
            content=content, file_name=file_name, accepted_types=type_to_load
        )

    def _build(self):
        # The params dict is used to build the module
        # it contains values and keys that point to nodes which
        # have their own params dict
        # When build is called, we iterate through the params dict
        # and if the value is a node, we call build on that node
        # and use the output of that build as the value for the param
        # if the value is not a node, then we use the value as the param
        # and continue
        # Another aspect is that the node_type is the class that we need to import
        # and instantiate with these built params
        logger.debug(f"Building {self.vertex_type}")
        # Build each node in the params dict
        for key, value in self.params.copy().items():
            # Check if Node or list of Nodes and not self
            # to avoid recursion
            if isinstance(value, ContractEdge):
                if value == self:
                    del self.params[key]
                    continue
                result = value.get_result()
                # If the key is "func", then we need to use the run method
                if key == "func":
                    if not isinstance(result, types.FunctionType):
                        # func can be
                        # PythonFunction(code='\ndef upper_case(text: str) -> str:\n    return text.upper()\n')
                        # so we need to check if there is an attribute called run
                        if hasattr(result, "run"):
                            result = result.run  # type: ignore
                        elif hasattr(result, "get_function"):
                            result = result.get_function()  # type: ignore
                    elif inspect.iscoroutinefunction(result):
                        self.params["coroutine"] = result
                    else:
                        # turn result which is a function into a coroutine
                        # so that it can be awaited
                        self.params["coroutine"] = sync_to_async(result)
                if isinstance(result, list):
                    # If the result is a list, then we need to extend the list
                    # with the result but first check if the key exists
                    # if it doesn't, then we need to create a new list
                    if isinstance(self.params[key], list):
                        self.params[key].extend(result)

                self.params[key] = result
            elif isinstance(value, list) and all(
                isinstance(edge, ContractEdge) for edge in value
            ):
                self.params[key] = []
                for edge in value:
                    built = edge.get_result()
                    if isinstance(built, list):
                        self.params[key].extend(built)
                    else:
                        self.params[key].append(built)

        # Get the class from LANGCHAIN_TYPES_DICT
        # and instantiate it with the params
        # and return the instance

        try:
            self._built_object = loading.instantiate_class(
                node_type=self.vertex_type,
                base_type=self.base_type,  # type: ignore
                params=self.params,
            )
        except Exception as exc:
            logger.exception(exc)
            raise ValueError(
                f"Error building Vertex {self.vertex_type}: {str(exc)}"
            ) from exc

        if self._built_object is None:
            raise ValueError(f"Vertex type {self.vertex_type} not found")

        self._built = True

    def build(self, force: bool = False) -> Any:
        if not self._built or force:
            self._build()
            self.fulfill_contracts()

        return self._built_object

    def fulfill_contracts(self):
        for edge in self.edges:
            if edge.source == self:
                edge.fulfill()

    def add_edge(self, edge: "ContractEdge") -> None:
        self.edges.append(edge)

    def __repr__(self) -> str:
        return f"Vertex(id={self.id}, data={self.data})"

    def __eq__(self, __o: object) -> bool:
        return self.id == __o.id if isinstance(__o, Vertex) else False

    def __hash__(self) -> int:
        return id(self)

    def _built_object_repr(self):
        return repr(self._built_object)
