# Description: Graph class for building a graph of nodes and edges
# Insights:
#   - Defer prompts building to the last moment or when they have all the tools
#   - Build each inner agent first, then build the outer agent

import types
from copy import deepcopy
from typing import Any, Dict, List, Optional

from langflow.graph.constants import DIRECT_TYPES
from langflow.graph.utils import load_file
from langflow.interface import loading
from langflow.interface.listing import ALL_TYPES_DICT
from langflow.utils.logger import logger


class Node:
    def __init__(self, data: Dict, base_type: Optional[str] = None) -> None:
        self.id: str = data["id"]
        self._data = data
        self.edges: List[Edge] = []
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
        self.node_type = (
            self.data["type"] if "Tool" not in self.output else template_dict["_type"]
        )
        if self.base_type is None:
            for base_type, value in ALL_TYPES_DICT.items():
                if self.node_type in value:
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
                loaded_dict = load_file(file_name, content, type_to_load)
                params[key] = loaded_dict

            # We should check if the type is in something not
            # the opposite
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
                        f"Required input {key} for module {self.node_type} not found"
                    )
                elif value["list"]:
                    # If this is a list parameter, append all sources to a list
                    params[key] = [edge.source for edge in edges]
                elif edges:
                    # If a single parameter is found, use its source
                    params[key] = edges[0].source

            elif value["required"] or value.get("value"):
                params[key] = value["value"]

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
        logger.debug(f"Building {self.node_type}")
        # Build each node in the params dict
        for key, value in self.params.copy().items():
            # Check if Node or list of Nodes and not self
            # to avoid recursion
            if isinstance(value, Node):
                if value == self:
                    del self.params[key]
                    continue
                result = value.build()
                # If the key is "func", then we need to use the run method
                if key == "func" and not isinstance(result, types.FunctionType):
                    # func can be PythonFunction(code='\ndef upper_case(text: str) -> str:\n    return text.upper()\n')
                    # so we need to check if there is an attribute called run
                    if hasattr(result, "run"):
                        result = result.run  # type: ignore
                    elif hasattr(result, "get_function"):
                        result = result.get_function()  # type: ignore
                self.params[key] = result
            elif isinstance(value, list) and all(
                isinstance(node, Node) for node in value
            ):
                self.params[key] = [node.build() for node in value]  # type: ignore

        # Get the class from LANGCHAIN_TYPES_DICT
        # and instantiate it with the params
        # and return the instance

        try:
            self._built_object = loading.instantiate_class(
                node_type=self.node_type,
                base_type=self.base_type,
                params=self.params,
            )
        except Exception as exc:
            raise ValueError(
                f"Error building node {self.node_type}: {str(exc)}"
            ) from exc

        if self._built_object is None:
            raise ValueError(f"Node type {self.node_type} not found")

        self._built = True

    def build(self, force: bool = False) -> Any:
        if not self._built or force:
            self._build()
        return deepcopy(self._built_object)

    def add_edge(self, edge: "Edge") -> None:
        self.edges.append(edge)

    def __repr__(self) -> str:
        return f"Node(id={self.id}, data={self.data})"

    def __eq__(self, __o: object) -> bool:
        return self.id == __o.id if isinstance(__o, Node) else False

    def __hash__(self) -> int:
        return id(self)


class Edge:
    def __init__(self, source: "Node", target: "Node"):
        self.source: "Node" = source
        self.target: "Node" = target
        self.validate_edge()

    def validate_edge(self) -> None:
        # Validate that the outputs of the source node are valid inputs
        # for the target node
        self.source_types = self.source.output
        self.target_reqs = self.target.required_inputs + self.target.optional_inputs
        # Both lists contain strings and sometimes a string contains the value we are
        # looking for e.g. comgin_out=["Chain"] and target_reqs=["LLMChain"]
        # so we need to check if any of the strings in source_types is in target_reqs
        self.valid = any(
            output in target_req
            for output in self.source_types
            for target_req in self.target_reqs
        )
        # Get what type of input the target node is expecting

        self.matched_type = next(
            (
                output
                for output in self.source_types
                for target_req in self.target_reqs
                if output in target_req
            ),
            None,
        )
        no_matched_type = self.matched_type is None
        if no_matched_type:
            logger.debug(self.source_types)
            logger.debug(self.target_reqs)
        if no_matched_type:
            raise ValueError(
                f"Edge between {self.source.node_type} and {self.target.node_type} "
                f"has no matched type"
            )

    def __repr__(self) -> str:
        return (
            f"Edge(source={self.source.id}, target={self.target.id}, valid={self.valid}"
            f", matched_type={self.matched_type})"
        )
