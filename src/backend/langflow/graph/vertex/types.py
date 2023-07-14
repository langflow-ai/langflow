import ast
from typing import Any, Dict, List, Optional, Union

from langflow.graph.vertex.base import Vertex
from langflow.graph.utils import extract_input_variables_from_prompt, flatten_list
from copy import deepcopy

from langflow.interface.connectors.custom import ConnectorFunction


class ConnectorVertex(Vertex):
    _built_object: Any = None
    _built: bool = False
    can_be_root: bool = True

    def __init__(self, data: Dict) -> None:
        super().__init__(data, base_type="connectors")

    def _build(self) -> None:
        func = None
        for param, value in self.params.items():
            if param == "code":
                conn_func = ConnectorFunction(code=value)
                func = conn_func.get_function()

        if func is None:
            raise ValueError("Connector function not found")
        self._built_object = func
        self._built = True


class LangChainVertex(Vertex):
    pass


class AgentVertex(LangChainVertex):
    can_be_root: bool = True

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

        #! Cannot deepcopy VectorStore, VectorStoreRouter, or SQL agents
        if self.vertex_type in [
            "VectorStoreAgent",
            "VectorStoreRouterAgent",
            "SQLAgent",
        ]:
            return self._built_object
        return deepcopy(self._built_object)


class ToolVertex(LangChainVertex):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="tools")


class LLMVertex(LangChainVertex):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="llms")


class ToolkitVertex(LangChainVertex):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="toolkits")


class FileToolVertex(ToolVertex):
    def __init__(self, data: Dict):
        super().__init__(data)


class WrapperVertex(LangChainVertex):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="wrappers")

    def build(self, force: bool = False) -> Any:
        if not self._built or force:
            if "headers" in self.params:
                self.params["headers"] = ast.literal_eval(self.params["headers"])
            self._build()
        return deepcopy(self._built_object)


class DocumentLoaderVertex(LangChainVertex):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="documentloaders")

    def _built_object_repr(self):
        # This built_object is a list of documents. Maybe we should
        # show how many documents are in the list?

        if self._built_object:
            avg_length = sum(len(doc.page_content) for doc in self._built_object) / len(
                self._built_object
            )
            return f"""{self.vertex_type}({len(self._built_object)} documents)
            \nAvg. Document Length (characters): {avg_length}
            Documents: {self._built_object[:3]}..."""
        return f"{self.vertex_type}()"


class EmbeddingVertex(LangChainVertex):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="embeddings")


class VectorStoreVertex(LangChainVertex):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="vectorstores")


class MemoryVertex(LangChainVertex):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="memory")


class RetrieverVertex(Vertex):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="retrievers")


class TextSplitterVertex(Vertex):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="textsplitters")

    def _built_object_repr(self):
        # This built_object is a list of documents. Maybe we should
        # show how many documents are in the list?

        if self._built_object:
            avg_length = sum(len(doc.page_content) for doc in self._built_object) / len(
                self._built_object
            )
            return f"""{self.vertex_type}({len(self._built_object)} documents)
            \nAvg. Document Length (characters): {avg_length}
            \nDocuments: {self._built_object[:3]}..."""
        return f"{self.vertex_type}()"


class ChainVertex(LangChainVertex):
    can_be_root: bool = True

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

            if "prompt" not in self.params and "messages" not in self.params:
                for param in prompt_params:
                    prompt_text = self.params[param]
                    variables = extract_input_variables_from_prompt(prompt_text)
                    self.params["input_variables"].extend(variables)
                self.params["input_variables"] = list(
                    set(self.params["input_variables"])
                )
            else:
                self.params.pop("input_variables", None)

            self._build()
        return self._built_object

    def _built_object_repr(self):
        if (
            not self.artifacts
            or self._built_object is None
            or not hasattr(self._built_object, "format")
        ):
            return super()._built_object_repr()
        # We'll build the prompt with the artifacts
        # to show the user what the prompt looks like
        # with the variables filled in
        artifacts = self.artifacts.copy()
        # Remove the handle_keys from the artifacts
        # so the prompt format doesn't break
        artifacts.pop("handle_keys", None)
        try:
            template = self._built_object.format(**artifacts)
            return (
                template
                if isinstance(template, str)
                else f"{self.vertex_type}({template})"
            )
        except KeyError:
            return str(self._built_object)


class OutputParserVertex(Vertex):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="output_parsers")
