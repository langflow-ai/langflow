from typing import List
from langflow.components.component.base import Component
from langflow.components.template import Template
from langflow.components.field import TemplateField


class IoComponent(Component):
    pass


class ChatComponent(IoComponent):
    description: str = "Use this component to chat with your flow."
    base_classes: List[str] = ["Text"]
    name: str = "Chat"
    display_name: str = ""
    # Field field_type would be Chain
    template: Template = Template(
        type_name="Chat",
        fields=[
            TemplateField(
                name="chain",
                required=True,
                field_type="Chain",
                placeholder="",
                is_list=False,
                show=True,
                multiline=False,
                value=None,
            )
        ],
    )


class FormComponent(IoComponent):
    description: str = "Use this component to use your flow as a form."
    base_classes: List[str] = ["Form"]
    name: str = "Form"
    display_name: str = ""
    # Field field_type would be Chain
    template: Template = Template(
        type_name="Form",
        fields=[
            TemplateField(
                name="chain",
                required=True,
                field_type="Chain",
                placeholder="",
                is_list=False,
                show=True,
                multiline=False,
            ),
            # FormData
            TemplateField(
                name="form_data",
                required=True,
                field_type="code",
                placeholder="",
                is_list=False,
                show=True,
                multiline=False,
                value='{"question": "What is the meaning of life?"}',
            ),
        ],
    )
