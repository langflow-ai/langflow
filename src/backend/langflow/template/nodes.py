from typing import Optional

from langchain.agents import loading
from langchain.agents.mrkl import prompt

from langflow.template.base import FrontendNode, Template, TemplateField
from langflow.template.constants import DEFAULT_PROMPT, HUMAN_PROMPT, SYSTEM_PROMPT
from langflow.utils.constants import DEFAULT_PYTHON_FUNCTION

NON_CHAT_AGENTS = {
    agent_type: agent_class
    for agent_type, agent_class in loading.AGENT_TO_CLASS.items()
    if "chat" not in agent_type.value
}


class BasePromptFrontendNode(FrontendNode):
    name: str
    template: Template
    description: str
    base_classes: list[str]

    def to_dict(self):
        return super().to_dict()


class ZeroShotPromptNode(BasePromptFrontendNode):
    name: str = "ZeroShotPrompt"
    template: Template = Template(
        type_name="zero_shot",
        fields=[
            TemplateField(
                field_type="str",
                required=False,
                placeholder="",
                is_list=False,
                show=True,
                multiline=True,
                value=prompt.PREFIX,
                name="prefix",
            ),
            TemplateField(
                field_type="str",
                required=True,
                placeholder="",
                is_list=False,
                show=True,
                multiline=True,
                value=prompt.SUFFIX,
                name="suffix",
            ),
            TemplateField(
                field_type="str",
                required=False,
                placeholder="",
                is_list=False,
                show=True,
                multiline=True,
                value=prompt.FORMAT_INSTRUCTIONS,
                name="format_instructions",
            ),
        ],
    )
    description: str = "Prompt template for Zero Shot Agent."
    base_classes: list[str] = ["BasePromptTemplate"]

    def to_dict(self):
        return super().to_dict()


class PromptTemplateNode(FrontendNode):
    name: str = "PromptTemplate"
    template: Template
    description: str
    base_classes: list[str] = ["BasePromptTemplate"]

    def to_dict(self):
        return super().to_dict()


class PythonFunctionNode(FrontendNode):
    name: str = "PythonFunction"
    template: Template = Template(
        type_name="python_function",
        fields=[
            TemplateField(
                field_type="code",
                required=True,
                placeholder="",
                is_list=False,
                show=True,
                value=DEFAULT_PYTHON_FUNCTION,
                name="code",
            )
        ],
    )
    description: str = "Python function to be executed."
    base_classes: list[str] = ["function"]

    def to_dict(self):
        return super().to_dict()


class ToolNode(FrontendNode):
    name: str = "Tool"
    template: Template = Template(
        type_name="tool",
        fields=[
            TemplateField(
                field_type="str",
                required=True,
                placeholder="",
                is_list=False,
                show=True,
                multiline=True,
                value="",
                name="name",
            ),
            TemplateField(
                field_type="str",
                required=True,
                placeholder="",
                is_list=False,
                show=True,
                multiline=True,
                value="",
                name="description",
            ),
            TemplateField(
                field_type="str",
                required=True,
                placeholder="",
                is_list=False,
                show=True,
                multiline=True,
                value="",
                name="func",
            ),
        ],
    )
    description: str = "Tool to be used in the flow."
    base_classes: list[str] = ["BaseTool"]

    def to_dict(self):
        return super().to_dict()


class JsonAgentNode(FrontendNode):
    name: str = "JsonAgent"
    template: Template = Template(
        type_name="json_agent",
        fields=[
            TemplateField(
                field_type="BaseToolkit",
                required=True,
                show=True,
                name="toolkit",
            ),
            TemplateField(
                field_type="BaseLanguageModel",
                required=True,
                show=True,
                name="llm",
            ),
        ],
    )
    description: str = """Construct a json agent from an LLM and tools."""
    base_classes: list[str] = ["AgentExecutor"]

    def to_dict(self):
        return super().to_dict()


class InitializeAgentNode(FrontendNode):
    name: str = "initialize_agent"
    template: Template = Template(
        type_name="initailize_agent",
        fields=[
            TemplateField(
                field_type="str",
                required=True,
                is_list=True,
                show=True,
                multiline=False,
                options=list(NON_CHAT_AGENTS.keys()),
                value=list(NON_CHAT_AGENTS.keys())[0],
                name="agent",
            ),
            TemplateField(
                field_type="BaseChatMemory",
                required=False,
                show=True,
                name="memory",
            ),
            TemplateField(
                field_type="Tool",
                required=False,
                show=True,
                name="tools",
                is_list=True,
            ),
            TemplateField(
                field_type="BaseLanguageModel",
                required=True,
                show=True,
                name="llm",
            ),
        ],
    )
    description: str = """Construct a json agent from an LLM and tools."""
    base_classes: list[str] = ["AgentExecutor"]

    def to_dict(self):
        return super().to_dict()

    @staticmethod
    def format_field(field: TemplateField, name: Optional[str] = None) -> None:
        # do nothing and don't return anything
        pass


class CSVAgentNode(FrontendNode):
    name: str = "CSVAgent"
    template: Template = Template(
        type_name="csv_agent",
        fields=[
            TemplateField(
                field_type="file",
                required=True,
                show=True,
                name="path",
                value="",
                suffixes=[".csv"],
                fileTypes=["csv"],
            ),
            TemplateField(
                field_type="BaseLanguageModel",
                required=True,
                show=True,
                name="llm",
            ),
        ],
    )
    description: str = """Construct a json agent from a CSV and tools."""
    base_classes: list[str] = ["AgentExecutor"]

    def to_dict(self):
        return super().to_dict()


class PromptFrontendNode(FrontendNode):
    @staticmethod
    def format_field(field: TemplateField, name: Optional[str] = None) -> None:
        # if field.field_type  == "StringPromptTemplate"
        # change it to str
        PROMPT_FIELDS = [
            "template",
            "suffix",
            "prefix",
            "examples",
        ]
        if field.field_type == "StringPromptTemplate" and "Message" in str(name):
            field.field_type = "prompt"
            field.multiline = True
            field.value = HUMAN_PROMPT if "Human" in field.name else SYSTEM_PROMPT
        if field.name == "template" and field.value == "":
            field.value = DEFAULT_PROMPT

        if field.name in PROMPT_FIELDS:
            field.field_type = "prompt"

        if (
            "Union" in field.field_type
            and "BaseMessagePromptTemplate" in field.field_type
        ):
            field.field_type = "BaseMessagePromptTemplate"


class MemoryFrontendNode(FrontendNode):
    @staticmethod
    def format_field(field: TemplateField, name: Optional[str] = None) -> None:
        FrontendNode.format_field(field, name)

        if not isinstance(field.value, str):
            field.value = None
        if field.name == "k":
            field.required = True
            field.show = True
            field.field_type = "int"
            field.value = 10
            field.display_name = "Memory Size"
