import tempfile
import time

import certifi
from langchain_community.vectorstores import MongoDBAtlasVectorSearch
from pymongo.collection import Collection
from pymongo.operations import SearchIndexModel

from langflow.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from langflow.helpers.data import docs_to_data
from langflow.io import BoolInput, DropdownInput, HandleInput, IntInput, SecretStrInput, StrInput
from langflow.schema import Data


class MongoVectorStoreComponent(LCVectorStoreComponent):
    display_name = "MongoDB Atlas"
    description = "MongoDB Atlas Vector Store with search capabilities"
    name = "MongoDBAtlasVector"
    icon = "MongoDB"
    INSERT_MODES = ["append", "overwrite"]
    SIMILARITY_OPTIONS = ["cosine", "euclidean", "dotProduct"]
    QUANTIZATION_OPTIONS = ["scalar", "binary"]
    inputs = [
        SecretStrInput(name="mongodb_atlas_cluster_uri", display_name="MongoDB Atlas Cluster URI", required=True),
        BoolInput(name="enable_mtls", display_name="Enable mTLS", value=False, advanced=True, required=True),
        SecretStrInput(
            name="mongodb_atlas_client_cert",
            display_name="MongoDB Atlas Combined Client Certificate",
            required=False,
            info="Client Certificate combined with the private key in the following format:\n "
            "-----BEGIN PRIVATE KEY-----\n...\n -----END PRIVATE KEY-----\n-----BEGIN CERTIFICATE-----\n"
            "...\n-----END CERTIFICATE-----\n",
        ),
        StrInput(name="db_name", display_name="Database Name", required=True),
        StrInput(name="collection_name", display_name="Collection Name", required=True),
        StrInput(
            name="index_name",
            display_name="Index Name",
            required=True,
            info="The name of Atlas Search index, it should be a Vector Search.",
        ),
        *LCVectorStoreComponent.inputs,
        DropdownInput(
            name="insert_mode",
            display_name="Insert Mode",
            options=INSERT_MODES,
            value=INSERT_MODES[0],
            info="How to insert new documents into the collection.",
            advanced=True,
        ),
        HandleInput(name="embedding", display_name="Embedding", input_types=["Embeddings"]),
        IntInput(
            name="number_of_results",
            display_name="Number of Results",
            info="Number of results to return.",
            value=4,
            advanced=True,
        ),
        StrInput(
            name="index_field",
            display_name="Index Field",
            advanced=True,
            required=True,
            info="The field to index.",
            value="embedding",
        ),
        StrInput(
            name="filter_field", display_name="Filter Field", advanced=True, info="The field to filter the index."
        ),
        IntInput(
            name="number_dimensions",
            display_name="Number of Dimensions",
            info="Embedding Context Length.",
            value=1536,
            advanced=True,
            required=True,
        ),
        DropdownInput(
            name="similarity",
            display_name="Similarity",
            options=SIMILARITY_OPTIONS,
            value=SIMILARITY_OPTIONS[0],
            info="The method used to measure the similarity between vectors.",
            advanced=True,
        ),
        DropdownInput(
            name="quantization",
            display_name="Quantization",
            options=QUANTIZATION_OPTIONS,
            value=None,
            info="Quantization reduces memory costs converting 32-bit floats to smaller data types",
            advanced=True,
        ),
    ]

    @check_cached_vector_store
    def build_vector_store(self) -> MongoDBAtlasVectorSearch:
        try:
            from pymongo import MongoClient
        except ImportError as e:
            msg = "Please install pymongo to use MongoDB Atlas Vector Store"
            raise ImportError(msg) from e

        # Create temporary files for the client certificate
        if self.enable_mtls:
            client_cert_path = None
            try:
                client_cert = self.mongodb_atlas_client_cert.replace(" ", "\n")
                client_cert = client_cert.replace("-----BEGIN\nPRIVATE\nKEY-----", "-----BEGIN PRIVATE KEY-----")
                client_cert = client_cert.replace(
                    "-----END\nPRIVATE\nKEY-----\n-----BEGIN\nCERTIFICATE-----",
                    "-----END PRIVATE KEY-----\n-----BEGIN CERTIFICATE-----",
                )
                client_cert = client_cert.replace("-----END\nCERTIFICATE-----", "-----END CERTIFICATE-----")
                with tempfile.NamedTemporaryFile(delete=False) as client_cert_file:
                    client_cert_file.write(client_cert.encode("utf-8"))
                    client_cert_path = client_cert_file.name

            except Exception as e:
                msg = f"Failed to write certificate to temporary file: {e}"
                raise ValueError(msg) from e

        try:
            mongo_client: MongoClient = (
                MongoClient(
                    self.mongodb_atlas_cluster_uri,
                    tls=True,
                    tlsCertificateKeyFile=client_cert_path,
                    tlsCAFile=certifi.where(),
                )
                if self.enable_mtls
                else MongoClient(self.mongodb_atlas_cluster_uri)
            )

            collection = mongo_client[self.db_name][self.collection_name]

        except Exception as e:
            msg = f"Failed to connect to MongoDB Atlas: {e}"
            raise ValueError(msg) from e

        # Convert DataFrame to Data if needed using parent's method
        self.ingest_data = self._prepare_ingest_data()

        documents = []
        for _input in self.ingest_data or []:
            if isinstance(_input, Data):
                documents.append(_input.to_lc_document())
            else:
                documents.append(_input)

        if documents:
            self.__insert_mode(collection)

            return MongoDBAtlasVectorSearch.from_documents(
                documents=documents, embedding=self.embedding, collection=collection, index_name=self.index_name
            )
        return MongoDBAtlasVectorSearch(embedding=self.embedding, collection=collection, index_name=self.index_name)

    def search_documents(self) -> list[Data]:
        from bson.objectid import ObjectId

        vector_store = self.build_vector_store()

        self.verify_search_index(vector_store._collection)

        if self.search_query and isinstance(self.search_query, str):
            docs = vector_store.similarity_search(
                query=self.search_query,
                k=self.number_of_results,
            )
            for doc in docs:
                doc.metadata = {
                    key: str(value) if isinstance(value, ObjectId) else value for key, value in doc.metadata.items()
                }

            data = docs_to_data(docs)
            self.status = data
            return data
        return []

    def __insert_mode(self, collection: Collection) -> None:
        if self.insert_mode == "overwrite":
            collection.delete_many({})  # Delete all documents while preserving collection structure

    def verify_search_index(self, collection: Collection) -> None:
        """Verify if the search index exists, if not, create it.

        Args:
            collection (Collection): The collection to verify the search index on.
        """
        indexes = collection.list_search_indexes()

        index_names_types = {idx["name"]: idx["type"] for idx in indexes}
        index_names = list(index_names_types.keys())
        index_type = index_names_types.get(self.index_name)
        if self.index_name not in index_names and index_type != "vectorSearch":
            collection.create_search_index(self.__create_index_definition())

            time.sleep(20)  # Give some time for index to be ready

    def __create_index_definition(self) -> SearchIndexModel:
        fields = [
            {
                "type": "vector",
                "path": self.index_field,
                "numDimensions": self.number_dimensions,
                "similarity": self.similarity,
                "quantization": self.quantization,
            }
        ]
        if self.filter_field:
            fields.append({"type": "filter", "path": self.filter_field})
        return SearchIndexModel(definition={"fields": fields}, name=self.index_name, type="vectorSearch")
