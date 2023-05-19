from langflow.template.field.base import TemplateField


class RootField(TemplateField):
    field_type: str = "root_connection"
    name: str = "text"
    display_name: str = "Text"
    required: bool = False
    show: bool = True
