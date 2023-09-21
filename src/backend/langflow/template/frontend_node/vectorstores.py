from typing import List, Optional

from langflow.template.field.base import TemplateField
from langflow.template.frontend_node.base import FrontendNode


BASIC_FIELDS = [
    "work_dir",
    "collection_name",
    "api_key",
    "location",
    "persist_directory",
    "persist",
    "weaviate_url",
    "index_name",
    "namespace",
    "folder_path",
    "table_name",
    "query_name",
    "supabase_url",
    "supabase_service_key",
    "mongodb_atlas_cluster_uri",
    "collection_name",
    "db_name",
]
ADVANCED_FIELDS = [
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
    "pinecone_api_key",
    "pinecone_env",
    "client_kwargs",
    "search_kwargs",
    "chroma_server_host",
    "chroma_server_http_port",
    "chroma_server_ssl_enabled",
    "chroma_server_grpc_port",
    "chroma_server_cors_allow_origins",
]


class VectorStoreFrontendNode(FrontendNode):
    def add_extra_fields(self) -> None:
        extra_fields: List[TemplateField] = []
        # Add search_kwargs field
        extra_field = TemplateField(
            name="search_kwargs",
            field_type="NestedDict",
            required=False,
            placeholder="",
            show=True,
            advanced=True,
            multiline=False,
            value="{}",
        )
        extra_fields.append(extra_field)
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
            # Add client_kwargs field
            extra_field2 = TemplateField(
                name="client_kwargs",
                field_type="code",
                required=False,
                placeholder="",
                show=True,
                advanced=True,
                multiline=False,
                value="{}",
            )
            extra_fields.extend((extra_field, extra_field2))

        elif self.template.type_name == "Chroma":
            # New bool field for persist parameter
            chroma_fields = [
                TemplateField(
                    name="persist",
                    field_type="bool",
                    required=False,
                    show=True,
                    advanced=False,
                    value=False,
                    display_name="Persist",
                ),
                # chroma_server_grpc_port: str | None = None,
                TemplateField(
                    name="chroma_server_host",
                    field_type="str",
                    required=False,
                    show=True,
                    advanced=True,
                    display_name="Chroma Server Host",
                ),
                TemplateField(
                    name="chroma_server_http_port",
                    field_type="str",
                    required=False,
                    show=True,
                    advanced=True,
                    display_name="Chroma Server HTTP Port",
                ),
                TemplateField(
                    name="chroma_server_ssl_enabled",
                    field_type="bool",
                    required=False,
                    show=True,
                    advanced=True,
                    value=False,
                    display_name="Chroma Server SSL Enabled",
                ),
                TemplateField(
                    name="chroma_server_grpc_port",
                    field_type="str",
                    required=False,
                    show=True,
                    advanced=True,
                    display_name="Chroma Server GRPC Port",
                ),
                TemplateField(
                    name="chroma_server_cors_allow_origins",
                    field_type="str",
                    required=False,
                    is_list=True,
                    show=True,
                    advanced=True,
                    display_name="Chroma Server CORS Allow Origins",
                ),
            ]

            extra_fields.extend(chroma_fields)
        elif self.template.type_name == "Pinecone":
            # add pinecone_api_key and pinecone_env
            extra_field = TemplateField(
                name="pinecone_api_key",
                field_type="str",
                required=False,
                placeholder="",
                show=True,
                advanced=True,
                multiline=False,
                password=True,
                value="",
            )
            extra_field2 = TemplateField(
                name="pinecone_env",
                field_type="str",
                required=False,
                placeholder="",
                show=True,
                advanced=True,
                multiline=False,
                value="",
            )
            extra_fields.extend((extra_field, extra_field2))
        elif self.template.type_name == "FAISS":
            extra_field = TemplateField(
                name="folder_path",
                field_type="str",
                required=False,
                placeholder="",
                show=True,
                advanced=True,
                multiline=False,
                display_name="Local Path",
                value="",
            )
            extra_field2 = TemplateField(
                name="index_name",
                field_type="str",
                required=False,
                show=True,
                advanced=False,
                value="",
                display_name="Index Name",
            )
            extra_fields.extend((extra_field, extra_field2))
        elif self.template.type_name == "SupabaseVectorStore":
            self.display_name = "Supabase"
            # Add table_name and query_name
            extra_field = TemplateField(
                name="table_name",
                field_type="str",
                required=False,
                placeholder="",
                show=True,
                advanced=True,
                multiline=False,
                value="",
            )
            extra_field2 = TemplateField(
                name="query_name",
                field_type="str",
                required=False,
                placeholder="",
                show=True,
                advanced=True,
                multiline=False,
                value="",
            )
            # Add supabase_url and supabase_service_key
            extra_field3 = TemplateField(
                name="supabase_url",
                field_type="str",
                required=False,
                placeholder="",
                show=True,
                advanced=True,
                multiline=False,
                value="",
            )
            extra_field4 = TemplateField(
                name="supabase_service_key",
                field_type="str",
                required=False,
                placeholder="",
                show=True,
                advanced=True,
                multiline=False,
                password=True,
                value="",
            )
            extra_fields.extend((extra_field, extra_field2, extra_field3, extra_field4))

        elif self.template.type_name == "MongoDBAtlasVectorSearch":
            self.display_name = "MongoDB Atlas"

            extra_field = TemplateField(
                name="mongodb_atlas_cluster_uri",
                field_type="str",
                required=False,
                placeholder="",
                show=True,
                advanced=True,
                multiline=False,
                display_name="MongoDB Atlas Cluster URI",
                value="",
            )
            extra_field2 = TemplateField(
                name="collection_name",
                field_type="str",
                required=False,
                placeholder="",
                show=True,
                advanced=True,
                multiline=False,
                display_name="Collection Name",
                value="",
            )
            extra_field3 = TemplateField(
                name="db_name",
                field_type="str",
                required=False,
                placeholder="",
                show=True,
                advanced=True,
                multiline=False,
                display_name="Database Name",
                value="",
            )
            extra_field4 = TemplateField(
                name="index_name",
                field_type="str",
                required=False,
                placeholder="",
                show=True,
                advanced=True,
                multiline=False,
                display_name="Index Name",
                value="",
            )
            extra_fields.extend((extra_field, extra_field2, extra_field3, extra_field4))

        if extra_fields:
            for field in extra_fields:
                self.template.add_field(field)

    def add_extra_base_classes(self) -> None:
        self.base_classes.extend(("BaseRetriever", "VectorStoreRetriever"))

    @staticmethod
    def format_field(field: TemplateField, name: Optional[str] = None) -> None:
        FrontendNode.format_field(field, name)
        # Define common field attributes

        # Check and set field attributes
        if field.name == "texts":
            # if field.name is "texts" it has to be replaced
            # when instantiating the vectorstores
            field.name = "documents"

            field.field_type = "Document"
            field.display_name = "Documents"
            field.required = False
            field.show = True
            field.advanced = False
            field.is_list = True
        elif "embedding" in field.name:
            # for backwards compatibility
            field.name = "embedding"
            field.required = True
            field.show = True
            field.advanced = False
            field.display_name = "Embedding"
            field.field_type = "Embeddings"

        elif field.name in BASIC_FIELDS:
            field.show = True
            field.advanced = False
            if field.name == "api_key":
                field.display_name = "API Key"
                field.password = True
            elif field.name == "location":
                field.value = ":memory:"
                field.placeholder = ":memory:"

        elif field.name in ADVANCED_FIELDS:
            field.show = True
            field.advanced = True
            if "key" in field.name:
                field.password = False

        elif field.name == "text_key":
            field.show = False
