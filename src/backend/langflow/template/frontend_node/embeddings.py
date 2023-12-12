from typing import Optional

from langflow.template.field.base import TemplateField
from langflow.template.frontend_node.base import FrontendNode


class EmbeddingFrontendNode(FrontendNode):
    def add_extra_fields(self) -> None:
        if "VertexAI" in self.template.type_name:
            # Add credentials field which should of type file.
            self.template.add_field(
                TemplateField(
                    field_type="file",
                    required=False,
                    show=True,
                    name="credentials",
                    value="",
                    file_types=[".json"],
                )
            )

    @staticmethod
    def format_vertex_field(field: TemplateField, name: str):
        if "VertexAI" in name:
            key = field.name or ""
            advanced_fields = [
                "verbose",
                "top_p",
                "top_k",
                "max_output_tokens",
            ]
            if key in advanced_fields:
                field.advanced = True
            show_fields = [
                "verbose",
                "project",
                "location",
                "credentials",
                "max_output_tokens",
                "model_name",
                "temperature",
                "top_p",
                "top_k",
            ]

            if key in show_fields:
                field.show = True

    @staticmethod
    def format_jina_fields(field: TemplateField):
        name = field.name or ""
        if "jina" in name:
            field.show = True
            field.advanced = False

        if "auth" in name or "token" in name:
            field.password = True
            field.show = True
            field.advanced = False

        if name == "jina_api_url":
            field.show = True
            field.advanced = True
            field.display_name = "Jina API URL"
            field.password = False

    @staticmethod
    def format_openai_fields(field: TemplateField):
        name = field.name or ""
        if "openai" in name:
            field.show = True
            field.advanced = True
            split_name = name.split("_")
            title_name = " ".join([s.capitalize() for s in split_name])
            field.display_name = title_name.replace("Openai", "OpenAI").replace("Api", "API")

        if "api_key" in name:
            field.password = True
            field.show = True
            field.advanced = False

    @staticmethod
    def format_field(field: TemplateField, name: Optional[str] = None) -> None:
        FrontendNode.format_field(field, name)
        if name and "vertex" in name.lower():
            EmbeddingFrontendNode.format_vertex_field(field, name)
        field.advanced = not field.required
        field.show = True
        key = field.name or ""
        if key == "headers":
            field.show = False
        if key == "model_kwargs":
            field.field_type = "dict"
            field.advanced = True
            field.show = True
        elif key in [
            "model_name",
            "temperature",
            "model_file",
            "model_type",
            "deployment_name",
            "credentials",
        ]:
            field.advanced = False
            field.show = True
        if key == "credentials":
            field.field_type = "file"
        if name == "VertexAI" and key not in [
            "callbacks",
            "client",
            "stop",
            "tags",
            "cache",
        ]:
            field.show = True

        # Format Jina fields
        EmbeddingFrontendNode.format_jina_fields(field)
        EmbeddingFrontendNode.format_openai_fields(field)
