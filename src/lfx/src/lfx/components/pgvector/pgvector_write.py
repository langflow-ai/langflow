from langchain_community.vectorstores import PGVector
from langchain_core.documents import Document
from sqlalchemy.exc import SQLAlchemyError

from lfx.custom.custom_component.component import Component
from lfx.io import HandleInput, IntInput, Output, SecretStrInput, StrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.utils.connection_string_parser import transform_connection_string

LANGCHAIN_PGVECTOR_COLLECTION_TABLE = "langchain_pg_collection"
LANGCHAIN_PGVECTOR_EMBEDDING_TABLE = "langchain_pg_embedding"


def _parse_metadata_fields(metadata_fields: str | list[str] | None) -> list[str]:
    if not metadata_fields:
        return []
    if isinstance(metadata_fields, list):
        return [field.strip() for field in metadata_fields if field and field.strip()]
    return [field.strip() for field in metadata_fields.split(",") if field.strip()]


def _data_to_document(data: Data, embedding_field: str, metadata_fields: list[str]) -> Document:
    data_dict = data.data.copy()
    if embedding_field not in data_dict:
        msg = f"Embedding Field '{embedding_field}' was not found in the input data."
        raise ValueError(msg)

    metadata_keys = metadata_fields or [key for key in data_dict if key != embedding_field]
    missing_metadata_fields = [key for key in metadata_keys if key not in data_dict]
    if missing_metadata_fields:
        msg = f"Metadata field(s) not found in the input data: {', '.join(missing_metadata_fields)}"
        raise ValueError(msg)
    metadata = {key: data_dict[key] for key in metadata_keys if key in data_dict and key != embedding_field}
    return Document(page_content=str(data_dict[embedding_field]), metadata=metadata)


def _prepare_documents(ingest_data, embedding_field: str, metadata_fields: str | list[str] | None) -> list[Document]:
    if not ingest_data:
        return []

    if not isinstance(ingest_data, list):
        ingest_data = [ingest_data]

    documents = []
    metadata_field_names = _parse_metadata_fields(metadata_fields)
    for _input in ingest_data:
        if isinstance(_input, DataFrame):
            documents.extend(
                _data_to_document(data, embedding_field, metadata_field_names) for data in _input.to_data_list()
            )
        elif isinstance(_input, Data):
            documents.append(_data_to_document(_input, embedding_field, metadata_field_names))
        elif isinstance(_input, Document):
            metadata = _input.metadata
            if metadata_field_names:
                metadata = {key: _input.metadata[key] for key in metadata_field_names if key in _input.metadata}
            documents.append(Document(page_content=_input.page_content, metadata=metadata))
        else:
            documents.append(_input)
    return documents


def _batch_documents(documents: list, batch_size: int):
    for index in range(0, len(documents), batch_size):
        yield documents[index : index + batch_size]


class PGVectorWriteComponent(Component):
    display_name = "PGVector Write"
    description = "Batch writes documents to a LangChain PGVector vector store, creating its schema when missing."
    name = "pgvector_write"
    icon = "cpu"
    metadata = {"keywords": ["pgvector", "postgres", "vector", "write", "batch"]}

    inputs = [
        SecretStrInput(name="pg_server_url", display_name="PostgreSQL Server Connection String", required=True),
        StrInput(
            name="collection_name",
            display_name="Collection Name",
            info=(
                "LangChain PGVector collection name. Documents are stored in the shared "
                f"{LANGCHAIN_PGVECTOR_EMBEDDING_TABLE} table and linked to this collection."
            ),
            required=True,
        ),
        HandleInput(
            name="ingest_data",
            display_name="Ingest Data",
            input_types=["Data", "DataFrame", "Table"],
            is_list=True,
            required=True,
        ),
        HandleInput(name="embedding", display_name="Embedding", input_types=["Embeddings"], required=True),
        StrInput(
            name="embedding_field",
            display_name="Embedding Field",
            info="Field to use as the text content for embeddings.",
            value="text",
            required=True,
        ),
        StrInput(
            name="metadata_fields",
            display_name="Metadata Fields",
            info=(
                "Comma-separated fields to store as metadata. "
                "Leave empty to use all fields except the embedding field."
            ),
            advanced=True,
        ),
        IntInput(
            name="batch_size",
            display_name="Batch Size",
            info="Number of documents to write in each batch.",
            value=100,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Write Summary", name="write_summary", method="write_documents"),
    ]

    def _build_or_create_vector_store(self, connection_string: str) -> PGVector:
        """Initialize LangChain PGVector, which creates extension/tables/collection when missing."""
        return PGVector.from_existing_index(
            embedding=self.embedding,
            collection_name=self.collection_name,
            connection_string=connection_string,
        )

    def _add_documents(self, vector_store: PGVector, documents: list[Document]) -> list[str]:
        try:
            return vector_store.add_documents(documents)
        except IndexError as e:
            msg = (
                "Embedding service returned fewer embeddings than requested. "
                "Check that the selected embedding model supports embeddings and that the API response includes "
                "one non-empty embedding for each input document."
            )
            raise ValueError(msg) from e
        except SQLAlchemyError as e:
            if "vector must have at least 1 dimension" in str(e):
                msg = (
                    "Embedding service returned an empty embedding vector. "
                    "Check the embedding model/API configuration before writing to PGVector."
                )
                raise ValueError(msg) from e
            raise

    def write_documents(self) -> DataFrame:
        embedding_field = (self.embedding_field or "").strip()
        if not embedding_field:
            msg = "Embedding Field is required."
            raise ValueError(msg)

        documents = _prepare_documents(self.ingest_data, embedding_field, self.metadata_fields)
        if not documents:
            msg = "No documents were provided to write to PGVector."
            raise ValueError(msg)

        batch_size = int(self.batch_size or 0)
        if batch_size <= 0:
            msg = "Batch Size must be greater than 0."
            raise ValueError(msg)

        connection_string_parsed = transform_connection_string(self.pg_server_url)
        batches = list(_batch_documents(documents, batch_size))

        vector_store = self._build_or_create_vector_store(connection_string_parsed)

        inserted_ids = []
        for batch in batches:
            inserted_ids.extend(self._add_documents(vector_store, batch))

        summary = DataFrame(
            [
                {
                    "collection_name": self.collection_name,
                    "documents_written": len(documents),
                    "batches_written": len(batches),
                    "batch_size": batch_size,
                    "embedding_field": embedding_field,
                    "metadata_fields": ", ".join(_parse_metadata_fields(self.metadata_fields)),
                    "storage_schema": "langchain_pgvector",
                    "embedding_table": LANGCHAIN_PGVECTOR_EMBEDDING_TABLE,
                    "collection_table": LANGCHAIN_PGVECTOR_COLLECTION_TABLE,
                    "creates_schema_if_missing": True,
                    "ids_returned": len(inserted_ids),
                }
            ]
        )
        self.status = summary
        return summary
