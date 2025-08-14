import json
from pathlib import Path
from typing import Any

from cryptography.fernet import InvalidToken
from langchain_chroma import Chroma
from loguru import logger

from langflow.custom import Component
from langflow.io import BoolInput, DropdownInput, IntInput, MessageTextInput, Output, SecretStrInput
from langflow.schema.data import Data
from langflow.schema.dataframe import DataFrame
from langflow.services.auth.utils import decrypt_api_key
from langflow.services.deps import get_settings_service

settings = get_settings_service().settings
knowledge_directory = settings.knowledge_bases_dir
if not knowledge_directory:
    msg = "Knowledge bases directory is not set in the settings."
    raise ValueError(msg)
KNOWLEDGE_BASES_ROOT_PATH = Path(knowledge_directory).expanduser()


class KBRetrievalComponent(Component):
    display_name = "Knowledge Retrieval"
    description = "Search and retrieve data from knowledge."
    icon = "database"
    name = "KBRetrieval"

    inputs = [
        DropdownInput(
            name="knowledge_base",
            display_name="Knowledge",
            info="Select the knowledge to load data from.",
            required=True,
            options=[
                str(d.name) for d in KNOWLEDGE_BASES_ROOT_PATH.iterdir() if not d.name.startswith(".") and d.is_dir()
            ]
            if KNOWLEDGE_BASES_ROOT_PATH.exists()
            else [],
            refresh_button=True,
            real_time_refresh=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="Embedding Provider API Key",
            info="API key for the embedding provider to generate embeddings.",
            advanced=True,
            required=False,
        ),
        MessageTextInput(
            name="search_query",
            display_name="Search Query",
            info="Optional search query to filter knowledge base data.",
        ),
        IntInput(
            name="top_k",
            display_name="Top K Results",
            info="Number of top results to return from the knowledge base.",
            value=5,
            advanced=True,
            required=False,
        ),
        BoolInput(
            name="include_metadata",
            display_name="Include Metadata",
            info="Whether to include all metadata and embeddings in the output. If false, only content is returned.",
            value=True,
            advanced=False,
        ),
    ]

    outputs = [
        Output(
            name="chroma_kb_data",
            display_name="Results",
            method="get_chroma_kb_data",
            info="Returns the data from the selected knowledge base.",
        ),
    ]

    def _get_knowledge_bases(self) -> list[str]:
        """Retrieve a list of available knowledge bases.

        Returns:
            A list of knowledge base names.
        """
        if not KNOWLEDGE_BASES_ROOT_PATH.exists():
            return []

        return [str(d.name) for d in KNOWLEDGE_BASES_ROOT_PATH.iterdir() if not d.name.startswith(".") and d.is_dir()]

    def update_build_config(self, build_config, field_value, field_name=None):  # noqa: ARG002
        if field_name == "knowledge_base":
            # Update the knowledge base options dynamically
            build_config["knowledge_base"]["options"] = self._get_knowledge_bases()

            # If the selected knowledge base is not available, reset it
            if build_config["knowledge_base"]["value"] not in build_config["knowledge_base"]["options"]:
                build_config["knowledge_base"]["value"] = None

        return build_config

    def _get_kb_metadata(self, kb_path: Path) -> dict:
        """Load and process knowledge base metadata."""
        metadata: dict[str, Any] = {}
        metadata_file = kb_path / "embedding_metadata.json"
        if not metadata_file.exists():
            logger.warning(f"Embedding metadata file not found at {metadata_file}")
            return metadata

        try:
            with metadata_file.open("r", encoding="utf-8") as f:
                metadata = json.load(f)
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from {metadata_file}")
            return {}

        # Decrypt API key if it exists
        if "api_key" in metadata and metadata.get("api_key"):
            settings_service = get_settings_service()
            try:
                decrypted_key = decrypt_api_key(metadata["api_key"], settings_service)
                metadata["api_key"] = decrypted_key
            except (InvalidToken, TypeError, ValueError) as e:
                logger.error(f"Could not decrypt API key. Please provide it manually. Error: {e}")
                metadata["api_key"] = None
        return metadata

    def _build_embeddings(self, metadata: dict):
        """Build embedding model from metadata."""
        provider = metadata.get("embedding_provider")
        model = metadata.get("embedding_model")
        api_key = metadata.get("api_key")
        chunk_size = metadata.get("chunk_size")

        # If user provided a key in the input, it overrides the stored one.
        if self.api_key and self.api_key.get_secret_value():
            api_key = self.api_key.get_secret_value()

        # Handle various providers
        if provider == "OpenAI":
            from langchain_openai import OpenAIEmbeddings

            if not api_key:
                msg = "OpenAI API key is required. Provide it in the component's advanced settings."
                raise ValueError(msg)
            return OpenAIEmbeddings(
                model=model,
                api_key=api_key,
                chunk_size=chunk_size,
            )
        if provider == "HuggingFace":
            from langchain_huggingface import HuggingFaceEmbeddings

            return HuggingFaceEmbeddings(
                model=model,
            )
        if provider == "Cohere":
            from langchain_cohere import CohereEmbeddings

            if not api_key:
                msg = "Cohere API key is required when using Cohere provider"
                raise ValueError(msg)
            return CohereEmbeddings(
                model=model,
                cohere_api_key=api_key,
            )
        if provider == "Custom":
            # For custom embedding models, we would need additional configuration
            msg = "Custom embedding models not yet supported"
            raise NotImplementedError(msg)
        # Add other providers here if they become supported in ingest
        msg = f"Embedding provider '{provider}' is not supported for retrieval."
        raise NotImplementedError(msg)

    def get_chroma_kb_data(self) -> DataFrame:
        """Retrieve data from the selected knowledge base by reading the Chroma collection.

        Returns:
            A DataFrame containing the data rows from the knowledge base.
        """
        kb_path = KNOWLEDGE_BASES_ROOT_PATH / self.knowledge_base

        metadata = self._get_kb_metadata(kb_path)
        if not metadata:
            msg = f"Metadata not found for knowledge base: {self.knowledge_base}. Ensure it has been indexed."
            raise ValueError(msg)

        # Build the embedder for the knowledge base
        embedding_function = self._build_embeddings(metadata)

        # Load vector store
        chroma = Chroma(
            persist_directory=str(kb_path),
            embedding_function=embedding_function,
            collection_name=self.knowledge_base,
        )

        # If a search query is provided, perform a similarity search
        if self.search_query:
            # Use the search query to perform a similarity search
            logger.info(f"Performing similarity search with query: {self.search_query}")
            results = chroma.similarity_search_with_score(
                query=self.search_query or "",
                k=self.top_k,
            )
        else:
            results = chroma.similarity_search(
                query=self.search_query or "",
                k=self.top_k,
            )

            # For each result, make it a tuple to match the expected output format
            results = [(doc, 0) for doc in results]  # Assign a dummy score of 0

        # If metadata is enabled, get embeddings for the results
        id_to_embedding = {}
        if self.include_metadata and results:
            doc_ids = [doc[0].metadata.get("_id") for doc in results if doc[0].metadata.get("_id")]

            # Only proceed if we have valid document IDs
            if doc_ids:
                # Access underlying client to get embeddings
                collection = chroma._client.get_collection(name=self.knowledge_base)
                embeddings_result = collection.get(where={"_id": {"$in": doc_ids}}, include=["embeddings", "metadatas"])

                # Create a mapping from document ID to embedding
                for i, metadata in enumerate(embeddings_result.get("metadatas", [])):
                    if metadata and "_id" in metadata:
                        id_to_embedding[metadata["_id"]] = embeddings_result["embeddings"][i]

        # Build output data based on include_metadata setting
        data_list = []
        for doc in results:
            if self.include_metadata:
                # Include all metadata, embeddings, and content
                kwargs = {
                    "content": doc[0].page_content,
                    **doc[0].metadata,
                }
                if self.search_query:
                    kwargs["_score"] = -1 * doc[1]
                kwargs["_embeddings"] = id_to_embedding.get(doc[0].metadata.get("_id"))
            else:
                # Only include content
                kwargs = {
                    "content": doc[0].page_content,
                }

            data_list.append(Data(**kwargs))

        # Return the DataFrame containing the data
        return DataFrame(data=data_list)
