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

        #! Cannot deepcopy VectorStore, VectorStoreRouter, or SQL agents
        if self.node_type in ["VectorStoreAgent", "VectorStoreRouterAgent", "SQLAgent"]:
            return self._built_object
        return deepcopy(self._built_object)


class ToolNode(Node):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="tools")


class PromptNode(Node):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="prompts")

    def build(
        self,
        force: bool = False,
        tools: Optional[Union[List[Node], List[ToolNode]]] = None,
    ) -> Any:
        if not self._built or force:
            if (
                "input_variables" not in self.params
                or self.params["input_variables"] is None
            ):
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

        #! Cannot deepcopy SQLDatabaseChain
        if self.node_type in ["SQLDatabaseChain"]:
            return self._built_object
        return deepcopy(self._built_object)


class LLMNode(Node):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="llms")


class ToolkitNode(Node):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="toolkits")


class FileToolNode(ToolNode):
    def __init__(self, data: Dict):
        super().__init__(data)


class WrapperNode(Node):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="wrappers")

    def build(self, force: bool = False) -> Any:
        if not self._built or force:
            if "headers" in self.params:
                self.params["headers"] = eval(self.params["headers"])
            self._build()
        return deepcopy(self._built_object)


class DocumentLoaderNode(Node):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="documentloaders")

    def _built_object_repr(self):
        # This built_object is a list of documents. Maybe we should
        # show how many documents are in the list?
        if self._built_object:
            return f"""{self.node_type}({len(self._built_object)} documents)
            Documents: {self._built_object[:3]}..."""
        return f"{self.node_type}()"


class EmbeddingNode(Node):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="embeddings")


class VectorStoreNode(Node):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="vectorstores")

    def _built_object_repr(self):
        return "Vector stores can take time to build. It will build on the first query."


class MemoryNode(Node):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="memory")


class TextSplitterNode(Node):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="textsplitters")

    def _built_object_repr(self):
        # This built_object is a list of documents. Maybe we should
        # show how many documents are in the list?
        if self._built_object:
            return f"""{self.node_type}({len(self._built_object)} documents)\nDocuments: {self._built_object[:3]}..."""
        return f"{self.node_type}()"
