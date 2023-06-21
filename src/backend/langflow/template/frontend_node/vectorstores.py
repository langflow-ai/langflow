from typing import Optional

from langflow.template.field.base import TemplateField
from langflow.template.frontend_node.base import FrontendNode


class VectorStoreFrontendNode(FrontendNode):
    def add_extra_fields(self) -> None:
        extra_field = None
        if self.template.type_name == "Weaviate":
            extra_field = TemplateField(
                name="weaviate_url",
                field_type="str",
                required=True,
                placeholder="http://localhost:8080",
                show=True,
                advanced=False,
                multiline=False,
                value="http://localhost:8080",
            )

        elif self.template.type_name == "Chroma":
            # New bool field for persist parameter
            extra_field = TemplateField(
                name="persist",
                field_type="bool",
                required=False,
                show=True,
                advanced=False,
                value=True,
                display_name="Persist",
            )
        if extra_field is not None:
            self.template.add_field(extra_field)

    def add_extra_base_classes(self) -> None:
        self.base_classes.append("BaseRetriever")

    @staticmethod
    def format_field(field: TemplateField, name: Optional[str] = None) -> None:
        FrontendNode.format_field(field, name)
        # Define common field attributes
        basic_fields = [
            "work_dir",
            "collection_name",
            "api_key",
            "location",
            "persist_directory",
            "persist",
        ]
        advanced_fields = [
            "n_dim",
            "key",
            "prefix",
            "distance_func",
            "content_payload_key",
            "metadata_payload_key",
            "timeout",
            "host",
            "path",
            "url",
            "port",
            "https",
            "prefer_grpc",
            "grpc_port",
        ]

        # Check and set field attributes
        if field.name == "texts":
            field.name = "documents"
            field.field_type = "TextSplitter"
            field.display_name = "Text Splitter"
            field.required = True
            field.show = True
            field.advanced = False

        elif "embedding" in field.name:
            # for backwards compatibility
            field.name = "embedding"
            field.required = True
            field.show = True
            field.advanced = False
            field.display_name = "Embedding"
            field.field_type = "Embeddings"

        elif field.name in basic_fields:
            field.show = True
            field.advanced = False
            if field.name == "api_key":
                field.display_name = "API Key"
                field.password = True
            elif field.name == "location":
                field.value = ":memory:"
                field.placeholder = ":memory:"

        elif field.name in advanced_fields:
            field.show = True
            field.advanced = True
            if "key" in field.name:
                field.password = False
