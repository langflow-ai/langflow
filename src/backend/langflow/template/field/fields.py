from langflow.template.field.base import TemplateField


class RootField(TemplateField):
    field_type: str = "Connection"
    name: str = "text"
    display_name: str = "Input"
    required: bool = False
    show: bool = True
