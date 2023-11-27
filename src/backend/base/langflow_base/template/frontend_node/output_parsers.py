from typing import Optional

from langflow_base.template.field.base import TemplateField
from langflow_base.template.frontend_node.base import FrontendNode


class OutputParserFrontendNode(FrontendNode):
    @staticmethod
    def format_field(field: TemplateField, name: Optional[str] = None) -> None:
        FrontendNode.format_field(field, name)
        field.show = True
