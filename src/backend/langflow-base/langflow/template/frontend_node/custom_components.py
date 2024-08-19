from typing import Optional

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
    display_name: Optional[str] = "CustomComponent"
    beta: bool = False
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
    description: Optional[str] = None
    base_classes: list[str] = []


class ComponentFrontendNode(FrontendNode):
    _format_template: bool = False
    name: str = "Component"
    display_name: Optional[str] = "Component"
    beta: bool = False
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
    description: Optional[str] = None
    base_classes: list[str] = []
