import ast
import json
from typing import Optional

from langflow.components.field.base import TemplateField
from langflow.components.component.base import Component


class UtilitiesComponent(Component):
    @staticmethod
    def format_field(field: TemplateField, name: Optional[str] = None) -> None:
        Component.format_field(field, name)
        # field.field_type could be "Literal['news', 'search', 'places', 'images']
        # we need to convert it to a list
        if "Literal" in field.field_type:
            field.options = ast.literal_eval(field.field_type.replace("Literal", ""))
            field.is_list = True
            field.field_type = "str"

        if isinstance(field.value, dict):
            field.field_type = "code"
            field.value = json.dumps(field.value, indent=4)
