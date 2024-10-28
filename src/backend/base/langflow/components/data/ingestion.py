import astrapy
from pydantic import BaseModel, Field
from unstructured_ingest.v2.interfaces import ProcessorConfig
from unstructured_ingest.v2.pipeline.pipeline import Pipeline
from unstructured_ingest.v2.processes.chunker import ChunkerConfig
from unstructured_ingest.v2.processes.connectors.astradb import (
    AstraDBAccessConfig,
    AstraDBConnectionConfig,
    AstraDBUploaderConfig,
    AstraDBUploadStagerConfig,
)
from unstructured_ingest.v2.processes.connectors.local import (
    LocalConnectionConfig,
    LocalDownloaderConfig,
    LocalIndexerConfig,
)
from unstructured_ingest.v2.processes.embedder import EmbedderConfig
from unstructured_ingest.v2.processes.partitioner import PartitionerConfig

from langflow.base.data.utils import TEXT_FILE_TYPES
from langflow.custom import Component
from langflow.inputs import DropdownInput, FileInput, SecretStrInput, StrInput
from langflow.io import Output
from langflow.schema import Data


class IngestionComponent(Component):
    display_name = "Data Ingestion with Astra DB"
    description = "Ingest files and folders into an Astra DB Collection"
    name = "Ingestion"

    inputs = [
        SecretStrInput(
            name="api_endpoint",
            display_name="Astra DB API Endpoint",
            info="API endpoint URL for the Astra DB service.",
            value="ASTRA_DB_API_ENDPOINT",
            required=True,
        ),
        SecretStrInput(
            name="token",
            display_name="Astra DB Application Token",
            info="Authentication token for accessing Astra DB.",
            value="ASTRA_DB_APPLICATION_TOKEN",
            required=True,
        ),
        StrInput(
            name="collection_name",
            display_name="Collection Name",
            info="The name of the collection within Astra DB where the vectors will be stored.",
            required=True,
        ),
        DropdownInput(
            name="file",
            display_name="File in Astra DB",
            info="Select an ingested file from Astra DB to output as Data",
            options=[],
            refresh_button=True,
        ),
        FileInput(
            name="path",
            display_name="File to Ingest to Astra DB",
            file_types=TEXT_FILE_TYPES,
            info=f"Supported file types: {', '.join(TEXT_FILE_TYPES)}",
            required=False,
        ),
        SecretStrInput(
            name="unstructured_api_key",
            display_name="Unstructured API Key",
            info="Authentication token for accessing the Unstructured Serverless API",
            value="UNSTRUCTURED_API_KEY",
            required=False,
            advanced=True,
        ),
        SecretStrInput(
            name="embedding_api_key",
            display_name="Embedding API Key",
            info="Embedding Provider token for generating embeddings.",
            value="EMBEDDING_API_KEY",
            required=False,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="File Result", name="file_result", method="file_wrapper"),
        Output(display_name="Ingest Result", name="ingest_result", method="ingest_wrapper"),
    ]

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None):
        my_wrapper = self.AstraDBCollectionWrapper(
            astra_db_api_endpoint=self.api_endpoint,
            astra_db_application_token=self.token,
            collection_name=self.collection_name,
            unstructured_api_key=self.unstructured_api_key,
            embedding_api_key=self.embedding_api_key,
        )

        my_collection = my_wrapper._connect()

        distinct_files = my_collection.distinct("metadata.metadata.filename")

        if "file" in build_config:
            del build_config["file"]

        new_parameter = DropdownInput(
            name="file",
            display_name="File in Astra DB",
            info="Select an ingested file from Astra DB to output as Data",
            options=distinct_files,
            refresh_button=True,
        ).to_dict()

        items = list(build_config.items())
        items.insert(3, ("file", new_parameter))

        # Clear the original dictionary and update with the modified items
        build_config.clear()
        build_config.update(items)

        return build_config

    class AstraDBCollectionWrapper(BaseModel):
        """Wrapper around an Astra DB Collection."""

        astra_db_api_endpoint: str = Field(..., alias="astra_db_api_endpoint")
        astra_db_application_token: str = Field(..., alias="astra_db_application_token")
        collection_name: str = Field(..., alias="collection_name")
        unstructured_api_key: str = Field(None, alias="unstructured_api_key")
        embedding_api_key: str = Field(None, alias="embedding_api_key")

        def __repr__(self):
            return (
                f"AstraDBCollectionWrapper("
                f"astra_db_api_endpoint='{self.astra_db_api_endpoint}', "
                f"collection_name='{self.collection_name}', "
            )

        def _connect(self):
            my_client = astrapy.DataAPIClient()

            my_database = my_client.get_database(
                api_endpoint=self.astra_db_api_endpoint,
                token=self.astra_db_application_token,
            )

            return my_database.get_collection(self.collection_name)

        def _options(self):
            my_collection = self._connect()

            return my_collection.options()

        def ingest_file(self, path):
            if not path:
                msg = "Please, upload a file to use this component."
                raise ValueError(msg)

            # resolved_path = self.resolve_path(path)  TODO: Restore?

            # Get the embedding provider
            embedding_provider = self._options().vector.service.provider
            embedding_dimension = self._options().vector.dimension

            Pipeline.from_configs(
                context=ProcessorConfig(),
                indexer_config=LocalIndexerConfig(input_path=path),
                downloader_config=LocalDownloaderConfig(),
                source_connection_config=LocalConnectionConfig(),
                partitioner_config=PartitionerConfig(
                    partition_by_api=bool(self.unstructured_api_key),
                    api_key=self.unstructured_api_key,
                ),
                chunker_config=ChunkerConfig(chunking_strategy="by_title"),
                embedder_config=EmbedderConfig(
                    embedding_provider=embedding_provider,
                    embedding_api_key=self.embedding_api_key,
                ),
                destination_connection_config=AstraDBConnectionConfig(
                    access_config=AstraDBAccessConfig(
                        api_endpoint=self.astra_db_api_endpoint,
                        token=self.astra_db_application_token,
                    )
                ),
                stager_config=AstraDBUploadStagerConfig(),
                uploader_config=AstraDBUploaderConfig(
                    collection_name=self.collection_name,
                    embedding_dimension=embedding_dimension,
                ),
            ).run()

    def _build_wrapper(
        self,
        api_endpoint: str,
        token: str,
        collection_name: str,
        unstructured_api_key: str | None = None,
        embedding_api_key: str | None = None,
    ):
        return self.AstraDBCollectionWrapper(
            astra_db_api_endpoint=api_endpoint,
            astra_db_application_token=token,
            collection_name=collection_name,
            unstructured_api_key=unstructured_api_key,
            embedding_api_key=embedding_api_key,
        )

    def ingest_wrapper(self) -> Data:
        if not self.path:
            self.status = "No new file ingested"
            return self.status

        # Get the inputs
        my_wrapper = self._build_wrapper(
            self.api_endpoint,
            self.token,
            self.collection_name,
            self.unstructured_api_key,
            self.embedding_api_key,
        )

        # Ingest the file
        result = my_wrapper.ingest_file(self.path)

        # Set the status
        self.status = result

        return result

    def file_wrapper(self) -> Data:
        # Get the inputs
        my_wrapper = self._build_wrapper(
            self.api_endpoint,
            self.token,
            self.collection_name,
            self.unstructured_api_key,
            self.embedding_api_key,
        )

        # Get the Astra DB Data
        my_collection = my_wrapper._connect()

        # Call the find operation
        cursor = my_collection.find(
            filter={"metadata.metadata.filename": self.file}
        )  # TODO: limit on rows?
        raw_data = list(cursor)
        data = [Data(data=result, text=result["content"]) for result in raw_data]

        self.status = data

        return data
