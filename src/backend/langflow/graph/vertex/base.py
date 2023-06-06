from langflow.cache import base as cache_utils
from langflow.graph.vertex.constants import DIRECT_TYPES
from langflow.interface import loading
from langflow.interface.listing import ALL_TYPES_DICT
from langflow.utils.logger import logger
from langflow.utils.util import sync_to_async


import contextlib
import inspect
import types
import warnings
from typing import Any, Dict, List, Optional
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langflow.graph.edge.base import Edge


class Vertex:
    def __init__(self, data: Dict, base_type: Optional[str] = None) -> None:
        self.id: str = data["id"]
        self._data = data
        self.edges: List["Edge"] = []
        self.base_type: Optional[str] = base_type
        self._parse_data()
        self._built_object = None
        self._built = False

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
            self.data["type"] if "Tool" not in self.output else template_dict["_type"]
        )
        if self.base_type is None:
            for base_type, value in ALL_TYPES_DICT.items():
                if self.vertex_type in value:
                    self.base_type = base_type
                    break

    def _build_params(self):
        # Some params are required, some are optional
        # but most importantly, some params are python base classes
        # like str and others are LangChain objects like LLMChain, BasePromptTemplate
        # so we need to be able to distinguish between the two

        # The dicts with "type" == "str" are the ones that are python base classes
        # and most likely have a "value" key

        # So for each key besides "_type" in the template dict, we have a dict
        # with a "type" key. If the type is not "str", then we need to get the
        # edge that connects to that node and get the Node with the required data
        # and use that as the value for the param
        # If the type is "str", then we need to get the value of the "value" key
        # and use that as the value for the param
        template_dict = {
            key: value
            for key, value in self.data["node"]["template"].items()
            if isinstance(value, dict)
        }
        params = {}
        for key, value in template_dict.items():
            if key == "_type":
                continue
            # If the type is not transformable to a python base class
            # then we need to get the edge that connects to this node
            if value.get("type") == "file":
                # Load the type in value.get('suffixes') using
                # what is inside value.get('content')
                # value.get('value') is the file name
                file_name = value.get("value")
                content = value.get("content")
                type_to_load = value.get("suffixes")
                file_path = cache_utils.save_binary_file(
                    content=content, file_name=file_name, accepted_types=type_to_load
                )

                params[key] = file_path

            elif value.get("type") not in DIRECT_TYPES:
                # Get the edge that connects to this node
                edges = [
                    edge
                    for edge in self.edges
                    if edge.target == self and edge.matched_type in value["type"]
                ]

                # Get the output of the node that the edge connects to
                # if the value['list'] is True, then there will be more
                # than one time setting to params[key]
                # so we need to append to a list if it exists
                # or create a new list if it doesn't

                if value["required"] and not edges:
                    # If a required parameter is not found, raise an error
                    raise ValueError(
                        f"Required input {key} for module {self.vertex_type} not found"
                    )
                elif value["list"]:
                    # If this is a list parameter, append all sources to a list
                    params[key] = [edge.source for edge in edges]
                elif edges:
                    # If a single parameter is found, use its source
                    params[key] = edges[0].source

            elif value["required"] or value.get("value"):
                # If value does not have value this still passes
                # but then gives a keyError
                # so we need to check if value has value
                new_value = value.get("value")
                if new_value is None:
                    warnings.warn(f"Value for {key} in {self.vertex_type} is None. ")
                if value.get("type") == "int":
                    with contextlib.suppress(TypeError, ValueError):
                        new_value = int(new_value)  # type: ignore
                params[key] = new_value

        # Add _type to params
        self.params = params

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
            if isinstance(value, Vertex):
                if value == self:
                    del self.params[key]
                    continue
                result = value.build()
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
                isinstance(node, Vertex) for node in value
            ):
                self.params[key] = []
                for node in value:
                    built = node.build()
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
                base_type=self.base_type,
                params=self.params,
            )
        except Exception as exc:
            raise ValueError(
                f"Error building node {self.vertex_type}: {str(exc)}"
            ) from exc

        if self._built_object is None:
            raise ValueError(f"Node type {self.vertex_type} not found")

        self._built = True

    def build(self, force: bool = False) -> Any:
        if not self._built or force:
            self._build()

        return self._built_object

    def add_edge(self, edge: "Edge") -> None:
        self.edges.append(edge)

    def __repr__(self) -> str:
        return f"Node(id={self.id}, data={self.data})"

    def __eq__(self, __o: object) -> bool:
        return self.id == __o.id if isinstance(__o, Vertex) else False

    def __hash__(self) -> int:
        return id(self)

    def _built_object_repr(self):
        return repr(self._built_object)
