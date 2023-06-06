from typing import Any, Dict, List, Optional, Union

from langflow.graph.vertex.base import Vertex
from langflow.graph.utils import flatten_list
from langflow.interface.utils import extract_input_variables_from_prompt


class AgentVertex(Vertex):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="agents")

        self.tools: List[Union[ToolkitVertex, ToolVertex]] = []
        self.chains: List[ChainVertex] = []

    def _set_tools_and_chains(self) -> None:
        for edge in self.edges:
            source_node = edge.source
            if isinstance(source_node, (ToolVertex, ToolkitVertex)):
                self.tools.append(source_node)
            elif isinstance(source_node, ChainVertex):
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

        return self._built_object


class ToolVertex(Vertex):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="tools")


class LLMVertex(Vertex):
    built_node_type = None
    class_built_object = None

    def __init__(self, data: Dict):
        super().__init__(data, base_type="llms")

    def build(self, force: bool = False) -> Any:
        # LLM is different because some models might take up too much memory
        # or time to load. So we only load them when we need them.ß
        if self.vertex_type == self.built_node_type:
            return self.class_built_object
        if not self._built or force:
            self._build()
            self.built_node_type = self.vertex_type
            self.class_built_object = self._built_object
        # Avoid deepcopying the LLM
        # that are loaded from a file
        return self._built_object


class ToolkitVertex(Vertex):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="toolkits")


class FileToolVertex(ToolVertex):
    def __init__(self, data: Dict):
        super().__init__(data)


class WrapperVertex(Vertex):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="wrappers")

    def build(self, force: bool = False) -> Any:
        if not self._built or force:
            if "headers" in self.params:
                self.params["headers"] = eval(self.params["headers"])
            self._build()
        return self._built_object


class DocumentLoaderVertex(Vertex):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="documentloaders")

    def _built_object_repr(self):
        # This built_object is a list of documents. Maybe we should
        # show how many documents are in the list?
        if self._built_object:
            return f"""{self.vertex_type}({len(self._built_object)} documents)
            Documents: {self._built_object[:3]}..."""
        return f"{self.vertex_type}()"


class EmbeddingVertex(Vertex):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="embeddings")


class VectorStoreVertex(Vertex):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="vectorstores")

    def _built_object_repr(self):
        return "Vector stores can take time to build. It will build on the first query."


class MemoryVertex(Vertex):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="memory")


class TextSplitterVertex(Vertex):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="textsplitters")

    def _built_object_repr(self):
        # This built_object is a list of documents. Maybe we should
        # show how many documents are in the list?
        if self._built_object:
            return f"""{self.vertex_type}({len(self._built_object)} documents)
            \nDocuments: {self._built_object[:3]}..."""
        return f"{self.vertex_type}()"


class ChainVertex(Vertex):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="chains")

    def build(
        self,
        force: bool = False,
        tools: Optional[List[Union[ToolkitVertex, ToolVertex]]] = None,
    ) -> Any:
        if not self._built or force:
            # Check if the chain requires a PromptVertex
            for key, value in self.params.items():
                if isinstance(value, PromptVertex):
                    # Build the PromptVertex, passing the tools if available
                    self.params[key] = value.build(tools=tools, force=force)

            self._build()

        return self._built_object


class PromptVertex(Vertex):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="prompts")

    def build(
        self,
        force: bool = False,
        tools: Optional[List[Union[ToolkitVertex, ToolVertex]]] = None,
    ) -> Any:
        if not self._built or force:
            if (
                "input_variables" not in self.params
                or self.params["input_variables"] is None
            ):
                self.params["input_variables"] = []
            # Check if it is a ZeroShotPrompt and needs a tool
            if "ShotPrompt" in self.vertex_type:
                tools = (
                    [tool_node.build() for tool_node in tools]
                    if tools is not None
                    else []
                )
                # flatten the list of tools if it is a list of lists
                # first check if it is a list
                if tools and isinstance(tools, list) and isinstance(tools[0], list):
                    tools = flatten_list(tools)
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
        return self._built_object
