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
        DropdownInput(
            name="data_mode",
            display_name="Choose Data Mode (Read/Ingest)",
            info="Either Read an Existing File, or Ingest a New File",
            options=["Read", "Ingest"],
            value="Read",
            real_time_refresh=True,
        ),
        SecretStrInput(
            name="api_endpoint",
            display_name="Astra DB API Endpoint",
            info="API endpoint URL for the Astra DB service.",
            value="ASTRA_DB_API_ENDPOINT",
            required=True,
            real_time_refresh=True,
        ),
        SecretStrInput(
            name="token",
            display_name="Astra DB Application Token",
            info="Authentication token for accessing Astra DB.",
            value="ASTRA_DB_APPLICATION_TOKEN",
            required=True,
            real_time_refresh=True,
        ),
    ]

    outputs = [
        Output(display_name="Read Result", name="read_result", method="read_wrapper"),
        Output(display_name="Ingest Result", name="ingest_result", method="ingest_wrapper"),
    ]

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None):
        if field_name in ["api_endpoint", "token"] and self.api_endpoint and self.token:
            print("HELLO!!!!")
            my_wrapper = self._build_wrapper(
                api_endpoint=self.api_endpoint,
                token=self.token,
            )
            print("AAA")

            my_database = my_wrapper._database()
            print("BBB")

            if "collection_name" in build_config:
                del build_config["collection_name"]

            print("CCCC")

            collection_options = my_database.list_collection_names()
            # collection_default = collection_options[0] if collection_options else None

            print("DDD")
            print(self.data_mode)
            param_0 = DropdownInput(
                name="collection_name",
                display_name="Astra DB Collection Name",
                info="Select the Astra DB Collection to use for data read/ingestion",
                options=collection_options,
                real_time_refresh=True,
                value=None,
            ).to_dict()
            print("EEE")
            print(self.data_mode)

            items = list(build_config.items())
            items.insert(len(items) - 1, ("collection_name", param_0))

            # Clear the original dictionary and update with the modified items
            build_config.clear()
            build_config.update(items)

        elif field_name == "data_mode" and hasattr(self, "collection_name"):
            if self.data_mode == "Read":
                print("WTF")
                for key in ["path", "unstructured_api_key", "embedding_api_key"]:
                    if key in build_config:
                        del build_config[key]

                print("Ok")

                my_wrapper = self._build_wrapper(
                    api_endpoint=self.api_endpoint,
                    token=self.token,
                    collection_name=self.collection_name,
                )

                print("Bye")

                my_collection = my_wrapper._collection()
                distinct_files = my_collection.distinct("metadata.metadata.filename")

                print("Hi")

                param_1 = DropdownInput(
                    name="file",
                    display_name="File to Read from Astra DB",
                    info="Select an ingested file from Astra DB to output as Data",
                    options=distinct_files,
                    refresh_button=True,
                    real_time_refresh=True,
                ).to_dict()

                items = list(build_config.items())
                items.insert(len(items) - 1, ("file", param_1))
            elif self.data_mode == "Ingest":
                for key in ["file"]:
                    if key in build_config:
                        del build_config[key]

                param_1 = FileInput(
                    name="path",
                    display_name="File to Ingest to Astra DB",
                    file_types=TEXT_FILE_TYPES,
                    info=f"Supported file types: {', '.join(TEXT_FILE_TYPES)}",
                    required=True,
                ).to_dict()
                param_2 = SecretStrInput(
                    name="unstructured_api_key",
                    display_name="Unstructured API Key",
                    info="Authentication token for accessing the Unstructured Serverless API",
                    required=False,
                ).to_dict()
                param_3 = SecretStrInput(
                    name="embedding_api_key",
                    display_name="Embedding API Key",
                    info="Embedding Provider token for generating embeddings.",
                    required=False,
                ).to_dict()

                items = list(build_config.items())
                items.insert(len(items) - 1, ("embedding_api_key", param_3))
                items.insert(len(items) - 1, ("unstructured_api_key", param_2))
                items.insert(len(items) - 1, ("path", param_1))

            # Clear the original dictionary and update with the modified items
            build_config.clear()
            build_config.update(items)

        return build_config

    class AstraDBWrapper(BaseModel):
        """Wrapper around an Astra DB Collection."""

        astra_db_api_endpoint: str = Field(..., alias="astra_db_api_endpoint")
        astra_db_application_token: str = Field(..., alias="astra_db_application_token")
        collection_name: str | None = Field(..., alias="collection_name")
        unstructured_api_key: str | None = Field(None, alias="unstructured_api_key")
        embedding_api_key: str | None = Field(None, alias="embedding_api_key")

        def __repr__(self):
            return (
                f"AstraDBWrapper("
                f"astra_db_api_endpoint='{self.astra_db_api_endpoint}', "
                f"collection_name='{self.collection_name}', "
            )

        def _database(self):
            my_client = astrapy.DataAPIClient()

            return my_client.get_database(
                api_endpoint=self.astra_db_api_endpoint,
                token=self.astra_db_application_token,
            )

        def _collection(self):
            my_database = self._database()

            return my_database.get_collection(self.collection_name)

        def _options(self):
            my_collection = self._collection()

            return my_collection.options()

        def ingest_file(self, path):
            if not path:
                msg = "Please, upload a file to use this component."
                raise ValueError(msg)

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
        collection_name: str | None = None,
        unstructured_api_key: str | None = None,
        embedding_api_key: str | None = None,
    ):
        return self.AstraDBWrapper(
            astra_db_api_endpoint=api_endpoint,
            astra_db_application_token=token,
            collection_name=collection_name,
            unstructured_api_key=unstructured_api_key,
            embedding_api_key=embedding_api_key,
        )

    def ingest_wrapper(self) -> Data:
        if not hasattr(self, "path"):
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

    def read_wrapper(self) -> Data:
        if not hasattr(self, "file"):
            self.status = "No file selected"
            return self.status

        # Get the inputs
        my_wrapper = self._build_wrapper(
            self.api_endpoint,
            self.token,
            self.collection_name,
        )

        # Get the Astra DB Data
        my_collection = my_wrapper._collection()

        # Call the find operation
        cursor = my_collection.find(filter={"metadata.metadata.filename": self.file})  # TODO: limit on rows?
        raw_data = list(cursor)
        data = [Data(data=result, text=result["content"]) for result in raw_data]

        self.status = data

        return data
