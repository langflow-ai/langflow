from langflow.template.field.base import TemplateField


class RootField(TemplateField):
    field_type: str = "Connection"
    name: str = "root_field"
    display_name: str = "Input"
    required: bool = False
    show: bool = True
    root: bool = True
