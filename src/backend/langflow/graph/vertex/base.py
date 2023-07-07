from langflow.interface.initialize import loading
from langflow.interface.listing import ALL_TYPES_DICT
from langflow.utils.constants import DIRECT_TYPES
from langflow.utils.logger import logger
from langflow.utils.util import sync_to_async


import inspect
import types
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
        self.artifacts: Dict[str, Any] = {}

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
        # Add the template_dicts[key]["input_types"] to the optional_inputs
        self.optional_inputs.extend(
            [
                input_type
                for value in template_dicts.values()
                for input_type in value.get("input_types", [])
            ]
        )

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
        # sourcery skip: merge-list-append, remove-redundant-if
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

        for edge in self.edges:
            param_key = edge.target_param
            if param_key in template_dict:
                if template_dict[param_key]["list"]:
                    if param_key not in params:
                        params[param_key] = []
                    params[param_key].append(edge.source)
                elif edge.target.id == self.id:
                    params[param_key] = edge.source

        for key, value in template_dict.items():
            if key == "_type" or not value.get("show"):
                continue
            # If the type is not transformable to a python base class
            # then we need to get the edge that connects to this node
            if value.get("type") == "file":
                # Load the type in value.get('suffixes') using
                # what is inside value.get('content')
                # value.get('value') is the file name
                file_path = value.get("file_path")

                params[key] = file_path
            elif value.get("type") in DIRECT_TYPES and params.get(key) is None:
                params[key] = value.get("value")

            if not value.get("required") and params.get(key) is None:
                if value.get("default"):
                    params[key] = value.get("default")
                else:
                    params.pop(key, None)
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
            if self.base_type is None:
                raise ValueError(f"Base type for node {self.vertex_type} not found")
            result = loading.instantiate_class(
                node_type=self.vertex_type,
                base_type=self.base_type,
                params=self.params,
            )
            # Result could be the _built_object or
            # (_built_object, dict) tuple
            if isinstance(result, tuple):
                self._built_object, self.artifacts = result
            else:
                self._built_object = result
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
        if edge not in self.edges:
            self.edges.append(edge)

    def __repr__(self) -> str:
        return f"Node(id={self.id}, data={self.data})"

    def __eq__(self, __o: object) -> bool:
        return self.id == __o.id if isinstance(__o, Vertex) else False

    def __hash__(self) -> int:
        return id(self)

    def _built_object_repr(self):
        # Add a message with an emoji, stars for sucess,
        return "Built sucessfully ✨" if self._built_object else "Failed to build 😵‍💫"
