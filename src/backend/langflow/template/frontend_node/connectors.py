from typing import Optional

from langflow.interface.connectors.custom import (
    DALL_E2_FUNCTION,
    DEFAULT_CONNECTOR_FUNCTION,
)
from langflow.template.field.base import TemplateField
from langflow.template.field.fields import RootField
from langflow.template.frontend_node.base import FrontendNode
from langflow.template.template.base import Template


class ConnectorFunctionFrontendNode(FrontendNode):
    name: str = "ConnectorFunction"
    # Template consists of an input of field_type "Output", name "input_connection"
    # and an output of field_type "Input", name "output_connection"

    template: Template = Template(
        type_name="ConnectorFunction",
        root_field=RootField(field_type="Text"),
        fields=[
            TemplateField(
                field_type="code",
                required=True,
                is_list=False,
                show=True,
                value=DEFAULT_CONNECTOR_FUNCTION,
                name="code",
                advanced=False,
            ),
        ],
    )
    description: str = """Connect two nodes together."""
    base_classes: list[str] = ["Text"]

    @staticmethod
    def format_field(field: TemplateField, name: Optional[str] = None) -> None:
        pass


class DallE2GeneratorFrontendNode(ConnectorFunctionFrontendNode):
    name: str = "DallE2Generator"
    # Template consists of an input of field_type "Output", name "input_connection"
    # and an output of field_type "Input", name "output_connection"

    template: Template = Template(
        type_name="DALL-E 2",
        root_field=RootField(field_type="Text"),
        fields=[
            TemplateField(
                field_type="code",
                required=True,
                is_list=False,
                show=False,
                value=DALL_E2_FUNCTION,
                name="code",
                advanced=False,
            ),
        ],
    )
    description: str = """Generate an image with DALL-E 2."""
    base_classes: list[str] = ["Text"]

    @staticmethod
    def format_field(field: TemplateField, name: Optional[str] = None) -> None:
        pass
