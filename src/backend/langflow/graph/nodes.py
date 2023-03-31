import json
from copy import deepcopy
from typing import Any, Dict, List, Optional, Union

from langflow.graph.base import Node
from langflow.interface.toolkits.base import toolkits_creator


class AgentNode(Node):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="agents")
        self.tools: List[ToolNode] = []
        self.chains: List[ChainNode] = []

    def _set_tools_and_chains(self) -> None:
        for edge in self.edges:
            source_node = edge.source
            if isinstance(source_node, ToolNode):
                self.tools.append(source_node)
            elif isinstance(source_node, ChainNode):
                self.chains.append(source_node)

    def build(self, force: bool = False) -> Any:
        if not self._built or force:
            self._set_tools_and_chains()
            # First, build the tools
            for tool_node in self.tools:
                tool_node.build()

            # Next, build the chains and the rest
            for chain_node in self.chains:
                chain_node.build(tools=self.tools)

            self._build()
        return deepcopy(self._built_object)


class ToolNode(Node):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="tools")

    def build(self, force: bool = False) -> Any:
        if not self._built or force:
            self._build()
        return deepcopy(self._built_object)


class PromptNode(Node):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="prompts")

    def build(
        self,
        force: bool = False,
        tools: Optional[Union[List[Node], List[ToolNode]]] = None,
    ) -> Any:
        if not self._built or force:
            # Check if it is a ZeroShotPrompt and needs a tool
            if self.node_type == "ZeroShotPrompt":
                tools = (
                    [tool_node.build() for tool_node in tools]
                    if tools is not None
                    else []
                )
                self.params["tools"] = tools

            self._build()
        return deepcopy(self._built_object)


class ChainNode(Node):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="chains")

    def build(
        self,
        force: bool = False,
        tools: Optional[Union[List[Node], List[ToolNode]]] = None,
    ) -> Any:
        if not self._built or force:
            # Check if the chain requires a PromptNode
            for key, value in self.params.items():
                if isinstance(value, PromptNode):
                    # Build the PromptNode, passing the tools if available
                    self.params[key] = value.build(tools=tools, force=force)

            self._build()
        return deepcopy(self._built_object)


class ToolkitNode(Node):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="toolkits")

    def build(self, force: bool = False) -> Any:
        if not self._built or force:
            if toolkits_creator.has_create_function(self.node_type):
                self.find_llm()
            self._build()
            # Now that the toolkit is built, we need to find the llm
            # and add it to the self.params

            # go through the edges and find the llm

        return deepcopy(self._built_object)

    def find_llm(self, node=None, edges_visited=[]) -> None:
        if node is None:
            node = self
        # Move recursively through the edges
        # the targets of this node edges are this node
        # If we find an LLMNode, we add it to the params
        if len(node.edges) == 1:
            return
        for edge in node.edges:
            source = edge.source
            if source in edges_visited:
                continue
            edges_visited.append(source)
            if isinstance(source, LLMNode):
                self.params["llm"] = source.build()
                break
            else:
                self.find_llm(source, edges_visited)


class LLMNode(Node):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="llms")

    def build(self, force: bool = False) -> Any:
        if not self._built or force:
            self._build()
        return deepcopy(self._built_object)


class FileToolNode(ToolNode):
    def __init__(self, data: Dict):
        super().__init__(data)

    def build(self, force: bool = False) -> Any:
        if not self._built or force:
            self._build()
        return deepcopy(self._built_object)


class WrapperNode(Node):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="wrappers")

    def build(self, force: bool = False) -> Any:
        if not self._built or force:
            if "headers" in self.params:
                self.params["headers"] = eval(self.params["headers"])
            self._build()
        return deepcopy(self._built_object)
