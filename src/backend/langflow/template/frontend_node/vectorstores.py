from typing import Optional

from langflow.template.field.base import TemplateField
from langflow.template.frontend_node.base import FrontendNode


class VectorStoreFrontendNode(FrontendNode):
    def add_extra_fields(self) -> None:
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

            self.template.add_field(extra_field)

    @staticmethod
    def format_field(field: TemplateField, name: Optional[str] = None) -> None:
        FrontendNode.format_field(field, name)
        # Define common field attributes
        basic_fields = ["work_dir", "collection_name", "api_key", "location"]
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
        # TODO: Weaviate requires weaviate_url to be passed as it is not part of
        # the class or from_texts method. We need the add_extra_fields to fix this
