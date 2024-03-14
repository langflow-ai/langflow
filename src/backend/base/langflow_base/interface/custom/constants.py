DEFAULT_CUSTOM_COMPONENT_CODE = """from langflow import CustomComponent
from typing import Optional, List, Dict, Union
from langflow_base.field_typing import (
    AgentExecutor,
    BaseChatMemory,
    BaseLanguageModel,
    BaseLLM,
    BaseLoader,
    BaseMemory,
    BaseOutputParser,
    BasePromptTemplate,
    BaseRetriever,
    Callable,
    Chain,
    ChatPromptTemplate,
    Data,
    Document,
    Embeddings,
    NestedDict,
    Object,
    PromptTemplate,
    TextSplitter,
    Tool,
    VectorStore,
)


class Component(CustomComponent):
    display_name: str = "Custom Component"
    description: str = "Create any custom component you want!"

    def build_config(self):
        return {"param": {"display_name": "Parameter"}}

    def build(self, param: Data) -> Data:
        return param

"""
