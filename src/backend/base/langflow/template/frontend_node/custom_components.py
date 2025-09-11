from langflow.template.field.base import Input
from langflow.template.frontend_node.base import FrontendNode
from langflow.template.template.base import Template

DEFAULT_CUSTOM_COMPONENT_CODE = """from langflow.custom import CustomComponent

from typing import Optional, List, Dict, Union
from langflow.field_typing import (
    AgentExecutor,
    BaseChatMemory,
    BaseLanguageModel,
    BaseLLM,
    BaseLoader,
    BaseMemory,
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


class CustomComponentFrontendNode(FrontendNode):
    _format_template: bool = False
    name: str = "CustomComponent"
    display_name: str | None = "CustomComponent"
    beta: bool = False
    legacy: bool = False
    minimized: bool = False
    template: Template = Template(
        type_name="CustomComponent",
        fields=[
            Input(
                field_type="code",
                required=True,
                placeholder="",
                is_list=False,
                show=True,
                value=DEFAULT_CUSTOM_COMPONENT_CODE,
                name="code",
                advanced=False,
                dynamic=True,
            )
        ],
    )
    description: str | None = None
    base_classes: list[str] = []
    last_updated: str | None = None


class ComponentFrontendNode(FrontendNode):
    _format_template: bool = False
    name: str = "Component"
    display_name: str | None = "Component"
    beta: bool = False
    minimized: bool = False
    legacy: bool = False
    template: Template = Template(
        type_name="Component",
        fields=[
            Input(
                field_type="code",
                required=True,
                placeholder="",
                is_list=False,
                show=True,
                value=DEFAULT_CUSTOM_COMPONENT_CODE,
                name="code",
                advanced=False,
                dynamic=True,
            )
        ],
    )
    description: str | None = None
    base_classes: list[str] = []
