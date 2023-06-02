from typing import Optional

from langflow.template.field.base import TemplateField
from langflow.template.frontend_node.base import FrontendNode


class EmbeddingFrontendNode(FrontendNode):
    @staticmethod
    def format_jina_fields(field: TemplateField):
        if "jina" in field.name:
            field.show = True
            field.advanced = False

        if "auth" in field.name or "token" in field.name:
            field.password = True
            field.show = True
            field.advanced = False

        if field.name == "jina_api_url":
            field.show = True
            field.advanced = True
            field.display_name = "Jina API URL"
            field.password = False

    @staticmethod
    def format_openai_fields(field: TemplateField):
        if "openai" in field.name:
            field.show = True
            field.advanced = True
            split_name = field.name.split("_")
            title_name = " ".join([s.capitalize() for s in split_name])
            field.display_name = title_name.replace("Openai", "OpenAI").replace(
                "Api", "API"
            )

        if "api_key" in field.name:
            field.password = True
            field.show = True
            field.advanced = False

    @staticmethod
    def format_field(field: TemplateField, name: Optional[str] = None) -> None:
        FrontendNode.format_field(field, name)
        field.advanced = not field.required
        field.show = True
        if field.name == "headers":
            field.show = False

        # Format Jina fields
        EmbeddingFrontendNode.format_jina_fields(field)
        EmbeddingFrontendNode.format_openai_fields(field)
