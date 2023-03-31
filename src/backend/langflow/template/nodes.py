from langchain.agents.mrkl import prompt

from langflow.template.base import Field, FrontendNode, Template
from langflow.utils.constants import DEFAULT_PYTHON_FUNCTION


class ZeroShotPromptNode(FrontendNode):
    name: str = "ZeroShotPrompt"
    template: Template = Template(
        type_name="zero_shot",
        fields=[
            Field(
                field_type="str",
                required=False,
                placeholder="",
                is_list=False,
                show=True,
                multiline=True,
                value=prompt.PREFIX,
                name="prefix",
            ),
            Field(
                field_type="str",
                required=True,
                placeholder="",
                is_list=False,
                show=True,
                multiline=True,
                value=prompt.SUFFIX,
                name="suffix",
            ),
            Field(
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


class PythonFunctionNode(FrontendNode):
    name: str = "PythonFunction"
    template: Template = Template(
        type_name="python_function",
        fields=[
            Field(
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
            Field(
                field_type="str",
                required=True,
                placeholder="",
                is_list=False,
                show=True,
                multiline=True,
                value="",
                name="name",
            ),
            Field(
                field_type="str",
                required=True,
                placeholder="",
                is_list=False,
                show=True,
                multiline=True,
                value="",
                name="description",
            ),
            Field(
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
            Field(
                field_type="BaseToolkit",
                required=True,
                show=True,
                name="toolkit",
            ),
            Field(
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
