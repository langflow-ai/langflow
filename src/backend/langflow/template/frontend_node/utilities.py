import ast
import json
from typing import Optional

from langflow.template.field.base import TemplateField
from langflow.template.frontend_node.base import FrontendNode


class UtilitiesFrontendNode(FrontendNode):
    @staticmethod
    def format_field(field: TemplateField, name: Optional[str] = None) -> None:
        FrontendNode.format_field(field, name)
        # field.field_type could be "Literal['news', 'search', 'places', 'images']
        # we need to convert it to a list
        if "Literal" in field.field_type:
            field.options = ast.literal_eval(field.field_type.replace("Literal", ""))
            field.is_list = True
            field.field_type = "str"

        if isinstance(field.value, dict):
            field.field_type = "code"
            field.value = json.dumps(field.value, indent=4)
