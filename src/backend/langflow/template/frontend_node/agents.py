from typing import Optional

from langchain.agents import types
from langflow.template.field.base import TemplateField
from langflow.template.frontend_node.base import FrontendNode
from langflow.template.template.base import Template

NON_CHAT_AGENTS = {
    agent_type: agent_class
    for agent_type, agent_class in types.AGENT_TO_CLASS.items()
    if "chat" not in agent_type.value
}


class AgentFrontendNode(FrontendNode):
    output_type: str = "Agent"

    @staticmethod
    def format_field(field: TemplateField, name: Optional[str] = None) -> None:
        if field.name in ["suffix", "prefix"]:
            field.show = True
        if field.name == "Tools" and name == "ZeroShotAgent":
            field.field_type = "BaseTool"
            field.is_list = True


class SQLAgentNode(FrontendNode):
    output_type: str = "Agent"
    name: str = "SQLAgent"
    template: Template = Template(
        type_name="sql_agent",
        fields=[
            TemplateField(
                field_type="str",  # pyright: ignore
                required=True,
                placeholder="",
                is_list=False,  # pyright: ignore
                show=True,
                multiline=False,
                value="",
                name="database_uri",
            ),
            TemplateField(
                field_type="BaseLanguageModel",  # pyright: ignore
                required=True,
                show=True,
                name="llm",
                display_name="LLM",
            ),
        ],
    )
    description: str = """Construct an SQL agent from an LLM and tools."""
    base_classes: list[str] = ["AgentExecutor"]


class VectorStoreRouterAgentNode(FrontendNode):
    output_type: str = "Agent"
    name: str = "VectorStoreRouterAgent"
    template: Template = Template(
        type_name="vectorstorerouter_agent",
        fields=[
            TemplateField(
                field_type="VectorStoreRouterToolkit",  # pyright: ignore
                required=True,
                show=True,
                name="vectorstoreroutertoolkit",
                display_name="Vector Store Router Toolkit",
            ),
            TemplateField(
                field_type="BaseLanguageModel",  # pyright: ignore
                required=True,
                show=True,
                name="llm",
                display_name="LLM",
            ),
        ],
    )
    description: str = """Construct an agent from a Vector Store Router."""
    base_classes: list[str] = ["AgentExecutor"]


class VectorStoreAgentNode(FrontendNode):
    output_type: str = "Agent"
    name: str = "VectorStoreAgent"
    template: Template = Template(
        type_name="vectorstore_agent",
        fields=[
            TemplateField(
                field_type="VectorStoreInfo",  # pyright: ignore
                required=True,
                show=True,
                name="vectorstoreinfo",
                display_name="Vector Store Info",
            ),
            TemplateField(
                field_type="BaseLanguageModel",  # pyright: ignore
                required=True,
                show=True,
                name="llm",
                display_name="LLM",
            ),
        ],
    )
    description: str = """Construct an agent from a Vector Store."""
    base_classes: list[str] = ["AgentExecutor"]


class SQLDatabaseNode(FrontendNode):
    output_type: str = "SQLDatabase"
    name: str = "SQLDatabase"
    template: Template = Template(
        type_name="sql_database",
        fields=[
            TemplateField(
                field_type="str",  # pyright: ignore
                required=True,
                is_list=False,  # pyright: ignore
                show=True,
                multiline=False,
                value="",
                name="uri",
            ),
        ],
    )
    description: str = """SQLAlchemy wrapper around a database."""
    base_classes: list[str] = ["SQLDatabase"]


class CSVAgentNode(FrontendNode):
    output_type: str = "Agent"
    name: str = "CSVAgent"
    template: Template = Template(
        type_name="csv_agent",
        fields=[
            TemplateField(
                field_type="file",  # pyright: ignore
                required=True,
                show=True,
                name="path",
                value="",
                file_types=[".csv"],  # pyright: ignore
            ),
            TemplateField(
                field_type="BaseLanguageModel",  # pyright: ignore
                required=True,
                show=True,
                name="llm",
                display_name="LLM",
            ),
        ],
    )
    description: str = """Construct a CSV agent from a CSV and tools."""
    base_classes: list[str] = ["AgentExecutor"]


class InitializeAgentNode(FrontendNode):
    output_type: str = "Agent"
    name: str = "AgentInitializer"
    display_name: str = "AgentInitializer"
    template: Template = Template(
        type_name="initialize_agent",
        fields=[
            TemplateField(
                field_type="str",  # pyright: ignore
                required=True,
                is_list=True,  # pyright: ignore
                show=True,
                multiline=False,
                options=list(NON_CHAT_AGENTS.keys()),
                value=list(NON_CHAT_AGENTS.keys())[0],
                name="agent",
                advanced=False,
            ),
            TemplateField(
                field_type="BaseChatMemory",  # pyright: ignore
                required=False,
                show=True,
                name="memory",
                advanced=False,
            ),
            TemplateField(
                field_type="Tool",  # pyright: ignore
                required=True,
                show=True,
                name="tools",
                is_list=True,  # pyright: ignore
                advanced=False,
            ),
            TemplateField(
                field_type="BaseLanguageModel",  # pyright: ignore
                required=True,
                show=True,
                name="llm",
                display_name="LLM",
                advanced=False,
            ),
        ],
    )
    description: str = """Construct a zero shot agent from an LLM and tools."""
    base_classes: list[str] = ["AgentExecutor", "Callable"]

    @staticmethod
    def format_field(field: TemplateField, name: Optional[str] = None) -> None:
        # do nothing and don't return anything
        pass


class JsonAgentNode(FrontendNode):
    output_type: str = "Agent"
    name: str = "JsonAgent"
    template: Template = Template(
        type_name="json_agent",
        fields=[
            TemplateField(
                field_type="BaseToolkit",  # pyright: ignore
                required=True,
                show=True,
                name="toolkit",
            ),
            TemplateField(
                field_type="BaseLanguageModel",  # pyright: ignore
                required=True,
                show=True,
                name="llm",
                display_name="LLM",
            ),
        ],
    )
    description: str = """Construct a json agent from an LLM and tools."""
    base_classes: list[str] = ["AgentExecutor"]
