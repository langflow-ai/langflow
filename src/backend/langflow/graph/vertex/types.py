import ast
from typing import Any, Dict, List, Optional, Union

from langflow.graph.vertex.base import Vertex
from langflow.graph.utils import flatten_list
from langflow.interface.utils import extract_input_variables_from_prompt


class AgentVertex(Vertex):
    def __init__(self, data: Dict, params: Optional[Dict] = None):
        super().__init__(data, base_type="agents", params=params)

        self.tools: List[Union[ToolkitVertex, ToolVertex]] = []
        self.chains: List[ChainVertex] = []

    def __getstate__(self):
        state = super().__getstate__()
        state["tools"] = self.tools
        state["chains"] = self.chains
        return state

    def __setstate__(self, state):
        self.tools = state["tools"]
        self.chains = state["chains"]
        super().__setstate__(state)

    def _set_tools_and_chains(self) -> None:
        for edge in self.edges:
            if not hasattr(edge, "source"):
                continue
            source_node = edge.source
            if isinstance(source_node, (ToolVertex, ToolkitVertex)):
                self.tools.append(source_node)
            elif isinstance(source_node, ChainVertex):
                self.chains.append(source_node)

    def build(self, force: bool = False, user_id=None, *args, **kwargs) -> Any:
        if not self._built or force:
            self._set_tools_and_chains()
            # First, build the tools
            for tool_node in self.tools:
                tool_node.build(user_id=user_id)

            # Next, build the chains and the rest
            for chain_node in self.chains:
                chain_node.build(tools=self.tools, user_id=user_id)

            self._build(user_id=user_id)

        return self._built_object


class ToolVertex(Vertex):
    def __init__(self, data: Dict, params: Optional[Dict] = None):
        super().__init__(data, base_type="tools", params=params)


class LLMVertex(Vertex):
    built_node_type = None
    class_built_object = None

    def __init__(self, data: Dict, params: Optional[Dict] = None):
        super().__init__(data, base_type="llms", params=params)

    def build(self, force: bool = False, user_id=None, *args, **kwargs) -> Any:
        # LLM is different because some models might take up too much memory
        # or time to load. So we only load them when we need them.ß
        if self.vertex_type == self.built_node_type:
            return self.class_built_object
        if not self._built or force:
            self._build(user_id=user_id)
            self.built_node_type = self.vertex_type
            self.class_built_object = self._built_object
        # Avoid deepcopying the LLM
        # that are loaded from a file
        return self._built_object


class ToolkitVertex(Vertex):
    def __init__(self, data: Dict, params=None):
        super().__init__(data, base_type="toolkits", params=params)


class FileToolVertex(ToolVertex):
    def __init__(self, data: Dict, params=None):
        super().__init__(data, params=params)


class WrapperVertex(Vertex):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="wrappers")

    def build(self, force: bool = False, user_id=None, *args, **kwargs) -> Any:
        if not self._built or force:
            if "headers" in self.params:
                self.params["headers"] = ast.literal_eval(self.params["headers"])
            self._build(user_id=user_id)
        return self._built_object


class DocumentLoaderVertex(Vertex):
    def __init__(self, data: Dict, params: Optional[Dict] = None):
        super().__init__(data, base_type="documentloaders", params=params)

    def _built_object_repr(self):
        # This built_object is a list of documents. Maybe we should
        # show how many documents are in the list?

        if self._built_object:
            avg_length = sum(
                len(doc.page_content)
                for doc in self._built_object
                if hasattr(doc, "page_content")
            ) / len(self._built_object)
            return f"""{self.vertex_type}({len(self._built_object)} documents)
            \nAvg. Document Length (characters): {int(avg_length)}
            Documents: {self._built_object[:3]}..."""
        return f"{self.vertex_type}()"


class EmbeddingVertex(Vertex):
    def __init__(self, data: Dict, params: Optional[Dict] = None):
        super().__init__(data, base_type="embeddings", params=params)


class VectorStoreVertex(Vertex):
    def __init__(self, data: Dict, params=None):
        super().__init__(data, base_type="vectorstores")

        self.params = params or {}

    # VectorStores may contain databse connections
    # so we need to define the __reduce__ method and the __setstate__ method
    # to avoid pickling errors
    def clean_edges_for_pickling(self):
        # for each edge that has self as source
        # we need to clear the _built_object of the target
        # so that we don't try to pickle a database connection
        for edge in self.edges:
            if edge.source == self:
                edge.target._built_object = None
                edge.target._built = False
                edge.target.params[edge.target_param] = self

    def remove_docs_and_texts_from_params(self):
        # remove documents and texts from params
        # so that we don't try to pickle a database connection
        self.params.pop("documents", None)
        self.params.pop("texts", None)

    def __getstate__(self):
        # We want to save the params attribute
        # and if "documents" or "texts" are in the params
        # we want to remove them because they have already
        # been processed.
        params = self.params.copy()
        params.pop("documents", None)
        params.pop("texts", None)
        self.clean_edges_for_pickling()

        return super().__getstate__()

    def __setstate__(self, state):
        super().__setstate__(state)
        self.remove_docs_and_texts_from_params()


class MemoryVertex(Vertex):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="memory")


class RetrieverVertex(Vertex):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="retrievers")


class TextSplitterVertex(Vertex):
    def __init__(self, data: Dict, params: Optional[Dict] = None):
        super().__init__(data, base_type="textsplitters", params=params)

    def _built_object_repr(self):
        # This built_object is a list of documents. Maybe we should
        # show how many documents are in the list?

        if self._built_object:
            avg_length = sum(len(doc.page_content) for doc in self._built_object) / len(
                self._built_object
            )
            return f"""{self.vertex_type}({len(self._built_object)} documents)
            \nAvg. Document Length (characters): {int(avg_length)}
            \nDocuments: {self._built_object[:3]}..."""
        return f"{self.vertex_type}()"


class ChainVertex(Vertex):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="chains")

    def build(
        self,
        force: bool = False,
        user_id=None,
        *args,
        **kwargs,
    ) -> Any:
        if not self._built or force:
            # Check if the chain requires a PromptVertex
            for key, value in self.params.items():
                if isinstance(value, PromptVertex):
                    # Build the PromptVertex, passing the tools if available
                    tools = kwargs.get("tools", None)
                    self.params[key] = value.build(tools=tools, force=force)

            self._build(user_id=user_id)

        return self._built_object


class PromptVertex(Vertex):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="prompts")

    def build(
        self,
        force: bool = False,
        user_id=None,
        tools: Optional[List[Union[ToolkitVertex, ToolVertex]]] = None,
        *args,
        **kwargs,
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
                    [tool_node.build(user_id=user_id) for tool_node in tools]
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
            elif isinstance(self.params, dict):
                self.params.pop("input_variables", None)

            self._build(user_id=user_id)
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
            if not hasattr(self._built_object, "template") and hasattr(
                self._built_object, "prompt"
            ):
                template = self._built_object.prompt.template
            else:
                template = self._built_object.template
            for key, value in artifacts.items():
                if value:
                    replace_key = "{" + key + "}"
                    template = template.replace(replace_key, value)
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


class CustomComponentVertex(Vertex):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="custom_components", is_task=True)

    def _built_object_repr(self):
        if self.task_id and self.is_task:
            if task := self.get_task():
                return str(task.info)
            else:
                return f"Task {self.task_id} is not running"
        if self.artifacts and "repr" in self.artifacts:
            return self.artifacts["repr"] or super()._built_object_repr()
