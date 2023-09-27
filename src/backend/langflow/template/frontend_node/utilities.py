import ast
from typing import Optional
from langflow.services.database.models.base import orjson_dumps

from langflow.template.field.base import TemplateField
from langflow.template.frontend_node.base import FrontendNode


class UtilitiesFrontendNode(FrontendNode):
    @staticmethod
    def format_field(field: TemplateField, name: Optional[str] = None) -> None:
        FrontendNode.format_field(field, name)
        # field.field_type could be "Literal['news', 'search', 'places', 'images']
        # we need to convert it to a list
        # It seems it could also be like "typing_extensions.['news', 'search', 'places', 'images']"
        if "Literal" in field.field_type:
            field_type = field.field_type.replace("typing_extensions.", "")
            field_type = field_type.replace("Literal", "")
            field.options = ast.literal_eval(field_type)
            field.is_list = True
            field.field_type = "str"

        if isinstance(field.value, dict):
            field.value = orjson_dumps(field.value)
