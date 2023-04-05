from copy import deepcopy
from typing import Any, Dict, List, Optional, Union

from langflow.graph.base import Node
from langflow.graph.utils import extract_input_variables_from_prompt


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
            if "input_variables" not in self.params:
                self.params["input_variables"] = []
            # Check if it is a ZeroShotPrompt and needs a tool
            if "ShotPrompt" in self.node_type:
                tools = (
                    [tool_node.build() for tool_node in tools]
                    if tools is not None
                    else []
                )
                self.params["tools"] = tools
                prompt_params = [
                    key
                    for key, value in self.params.items()
                    if isinstance(value, str) and key != "format_instructions"
                ]
            else:
                prompt_params = ["template"]
            for param in prompt_params:
                prompt_text = self.params[param]
                variables = extract_input_variables_from_prompt(prompt_text)

                self.params["input_variables"].extend(variables)
            self.params["input_variables"] = list(set(self.params["input_variables"]))

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


class LLMNode(Node):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="llms")

    def build(self, force: bool = False) -> Any:
        if not self._built or force:
            self._build()
        return deepcopy(self._built_object)


class ToolkitNode(Node):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="toolkits")

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


class MemoryNode(Node):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="memory")

    def build(self, force: bool = False) -> Any:
        if not self._built or force:
            self._build()
        return deepcopy(self._built_object)
