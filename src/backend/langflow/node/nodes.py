from langflow.node.template import Field, FrontendNode, Template
from langchain.agents.mrkl import prompt
from langflow.utils.constants import DEFAULT_PYTHON_FUNCTION


class ZeroShotPromptNode(FrontendNode):
    name = "ZeroShotPrompt"
    template = Template(
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
    description = "Prompt template for Zero Shot Agent."
    base_classes = ["BasePromptTemplate"]

    def to_dict(self):
        return super().to_dict()


class PythonFunctionNode(FrontendNode):
    name = "PythonFunction"
    template = Template(
        type_name="python_function",
        fields=[
            Field(
                field_type="str",
                required=True,
                placeholder="",
                is_list=False,
                show=True,
                multiline=True,
                value=DEFAULT_PYTHON_FUNCTION,
                name="code",
            ),
        ],
    )
    description = "Python function to be executed."
    base_classes = ["function"]

    def to_dict(self):
        return super().to_dict()


class ToolNode(FrontendNode):
    name = "Tool"
    template = Template(
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
    description = "Tool to be used in the flow."
    base_classes = ["BaseTool"]

    def to_dict(self):
        return super().to_dict()
