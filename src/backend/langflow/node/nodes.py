from langflow.node.template import Field, FrontendNode, Template
from langchain.agents.mrkl import prompt


class ZeroShotPromptNode(FrontendNode):
    _name = "ZeroShotPrompt"
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
