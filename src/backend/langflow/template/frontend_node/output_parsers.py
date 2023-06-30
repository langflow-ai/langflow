from typing import Optional
from langflow.template.field.base import TemplateField
from langflow.template.frontend_node.base import FrontendNode


class OutputParserFrontendNode(FrontendNode):
    @staticmethod
    def format_field(field: TemplateField, name: Optional[str] = None) -> None:
        FrontendNode.format_field(field, name)
        field.show = True
