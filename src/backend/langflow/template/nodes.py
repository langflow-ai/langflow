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

    @staticmethod
    def format_field(field: TemplateField, name: Optional[str] = None) -> None:
        FrontendNode.format_field(field, name)
        if field.name == "examples":
            field.advanced = False


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
                advanced=False,
            )
        ],
    )
    description: str = "Python function to be executed."
    base_classes: list[str] = ["function"]

    def to_dict(self):
        return super().to_dict()


class MidJourneyPromptChainNode(FrontendNode):
    name: str = "MidJourneyPromptChain"
    template: Template = Template(
        type_name="MidJourneyPromptChain",
        fields=[
            TemplateField(
                field_type="BaseLanguageModel",
                required=True,
                placeholder="",
                is_list=False,
                show=True,
                advanced=False,
                multiline=False,
                name="llm",
                display_name="LLM",
            ),
            TemplateField(
                field_type="BaseChatMemory",
                required=False,
                show=True,
                name="memory",
                advanced=False,
            ),
        ],
    )
    description: str = "MidJourneyPromptChain is a chain you can use to generate new MidJourney prompts."
    base_classes: list[str] = [
        "LLMChain",
        "BaseCustomChain",
        "Chain",
        "ConversationChain",
        "MidJourneyPromptChain",
    ]


class TimeTravelGuideChainNode(FrontendNode):
    name: str = "TimeTravelGuideChain"
    template: Template = Template(
        type_name="TimeTravelGuideChain",
        fields=[
            TemplateField(
                field_type="BaseLanguageModel",
                required=True,
                placeholder="",
                is_list=False,
                show=True,
                advanced=False,
                multiline=False,
                name="llm",
                display_name="LLM",
            ),
            TemplateField(
                field_type="BaseChatMemory",
                required=False,
                show=True,
                name="memory",
                advanced=False,
            ),
        ],
    )
    description: str = "Time travel guide chain to be used in the flow."
    base_classes: list[str] = [
        "LLMChain",
        "BaseCustomChain",
        "TimeTravelGuideChain",
        "Chain",
        "ConversationChain",
    ]


class SeriesCharacterChainNode(FrontendNode):
    name: str = "SeriesCharacterChain"
    template: Template = Template(
        type_name="SeriesCharacterChain",
        fields=[
            TemplateField(
                field_type="str",
                required=True,
                placeholder="",
                is_list=False,
                show=True,
                advanced=False,
                multiline=False,
                name="character",
            ),
            TemplateField(
                field_type="str",
                required=True,
                placeholder="",
                is_list=False,
                show=True,
                advanced=False,
                multiline=False,
                name="series",
            ),
            TemplateField(
                field_type="BaseLanguageModel",
                required=True,
                placeholder="",
                is_list=False,
                show=True,
                advanced=False,
                multiline=False,
                name="llm",
                display_name="LLM",
            ),
        ],
    )
    description: str = "SeriesCharacterChain is a chain you can use to have a conversation with a character from a series."  # noqa
    base_classes: list[str] = [
        "LLMChain",
        "BaseCustomChain",
        "Chain",
        "ConversationChain",
        "SeriesCharacterChain",
        "function",
    ]


class ToolNode(FrontendNode):
    name: str = "Tool"
    template: Template = Template(
        type_name="Tool",
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
                advanced=False,
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
                advanced=False,
            ),
            TemplateField(
                name="func",
                field_type="function",
                required=True,
                is_list=False,
                show=True,
                multiline=True,
                advanced=False,
            ),
            TemplateField(
                field_type="bool",
                required=True,
                placeholder="",
                is_list=False,
                show=True,
                multiline=False,
                value=False,
                name="return_direct",
            ),
        ],
    )
    description: str = "Tool to be used in the flow."
    base_classes: list[str] = ["Tool"]

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
                display_name="LLM",
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
                advanced=False,
            ),
            TemplateField(
                field_type="BaseChatMemory",
                required=False,
                show=True,
                name="memory",
                advanced=False,
            ),
            TemplateField(
                field_type="Tool",
                required=False,
                show=True,
                name="tools",
                is_list=True,
                advanced=False,
            ),
            TemplateField(
                field_type="BaseLanguageModel",
                required=True,
                show=True,
                name="llm",
                display_name="LLM",
                advanced=False,
            ),
        ],
    )
    description: str = """Construct a json agent from an LLM and tools."""
    base_classes: list[str] = ["AgentExecutor", "function"]

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
                display_name="LLM",
            ),
        ],
    )
    description: str = """Construct a json agent from a CSV and tools."""
    base_classes: list[str] = ["AgentExecutor"]

    def to_dict(self):
        return super().to_dict()


class SQLDatabaseNode(FrontendNode):
    name: str = "SQLDatabase"
    template: Template = Template(
        type_name="sql_database",
        fields=[
            TemplateField(
                field_type="str",
                required=True,
                is_list=False,
                show=True,
                multiline=False,
                value="",
                name="uri",
            ),
        ],
    )
    description: str = """SQLAlchemy wrapper around a database."""
    base_classes: list[str] = ["SQLDatabase"]

    def to_dict(self):
        return super().to_dict()


class VectorStoreAgentNode(FrontendNode):
    name: str = "VectorStoreAgent"
    template: Template = Template(
        type_name="vectorstore_agent",
        fields=[
            TemplateField(
                field_type="VectorStoreInfo",
                required=True,
                show=True,
                name="vectorstoreinfo",
                display_name="Vector Store Info",
            ),
            TemplateField(
                field_type="BaseLanguageModel",
                required=True,
                show=True,
                name="llm",
                display_name="LLM",
            ),
        ],
    )
    description: str = """Construct an agent from a Vector Store."""
    base_classes: list[str] = ["AgentExecutor"]

    def to_dict(self):
        return super().to_dict()


class VectorStoreRouterAgentNode(FrontendNode):
    name: str = "VectorStoreRouterAgent"
    template: Template = Template(
        type_name="vectorstorerouter_agent",
        fields=[
            TemplateField(
                field_type="VectorStoreRouterToolkit",
                required=True,
                show=True,
                name="vectorstoreroutertoolkit",
                display_name="Vector Store Router Toolkit",
            ),
            TemplateField(
                field_type="BaseLanguageModel",
                required=True,
                show=True,
                name="llm",
                display_name="LLM",
            ),
        ],
    )
    description: str = """Construct an agent from a Vector Store Router."""
    base_classes: list[str] = ["AgentExecutor"]

    def to_dict(self):
        return super().to_dict()


class SQLAgentNode(FrontendNode):
    name: str = "SQLAgent"
    template: Template = Template(
        type_name="sql_agent",
        fields=[
            TemplateField(
                field_type="str",
                required=True,
                placeholder="",
                is_list=False,
                show=True,
                multiline=False,
                value="",
                name="database_uri",
            ),
            TemplateField(
                field_type="BaseLanguageModel",
                required=True,
                show=True,
                name="llm",
                display_name="LLM",
            ),
        ],
    )
    description: str = """Construct an agent from a Vector Store Router."""
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
            "format_instructions",
        ]
        if field.field_type == "StringPromptTemplate" and "Message" in str(name):
            field.field_type = "prompt"
            field.multiline = True
            field.value = HUMAN_PROMPT if "Human" in field.name else SYSTEM_PROMPT
        if field.name == "template" and field.value == "":
            field.value = DEFAULT_PROMPT

        if field.name in PROMPT_FIELDS:
            field.field_type = "prompt"
            field.advanced = False

        if (
            "Union" in field.field_type
            and "BaseMessagePromptTemplate" in field.field_type
        ):
            field.field_type = "BaseMessagePromptTemplate"

        # All prompt fields should be password=False
        field.password = False


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
        field.password = False


class ChainFrontendNode(FrontendNode):
    @staticmethod
    def format_field(field: TemplateField, name: Optional[str] = None) -> None:
        FrontendNode.format_field(field, name)

        field.advanced = False
        if "key" in field.name:
            field.password = False
            field.show = False
        if field.name in ["input_key", "output_key"]:
            field.required = True
            field.show = True
            field.advanced = True

        # Separated for possible future changes
        if field.name == "prompt" and field.value is None:
            # if no prompt is provided, use the default prompt
            field.required = False
            field.show = True
            field.advanced = False
        if field.name == "memory":
            field.required = False
            field.show = True
            field.advanced = False
        if field.name == "verbose":
            field.required = False
            field.show = True
            field.advanced = True
        if field.name == "llm":
            field.required = True
            field.show = True
            field.advanced = False


class LLMFrontendNode(FrontendNode):
    @staticmethod
    def format_field(field: TemplateField, name: Optional[str] = None) -> None:
        display_names_dict = {
            "huggingfacehub_api_token": "HuggingFace Hub API Token",
        }
        FrontendNode.format_field(field, name)
        SHOW_FIELDS = ["repo_id"]
        if field.name in SHOW_FIELDS:
            field.show = True

        if "api" in field.name and ("key" in field.name or "token" in field.name):
            field.password = True
            field.show = True
            # Required should be False to support
            # loading the API key from environment variables
            field.required = False
            field.advanced = False

        if field.name == "task":
            field.required = True
            field.show = True
            field.is_list = True
            field.options = ["text-generation", "text2text-generation"]
            field.advanced = True

        if display_name := display_names_dict.get(field.name):
            field.display_name = display_name
        if field.name == "model_kwargs":
            field.field_type = "code"
            field.advanced = True
            field.show = True
        elif field.name in ["model_name", "temperature"]:
            field.advanced = False
            field.show = True


class EmbeddingFrontendNode(FrontendNode):
    @staticmethod
    def format_field(field: TemplateField, name: Optional[str] = None) -> None:
        FrontendNode.format_field(field, name)
        if field.name == "headers":
            field.show = False
