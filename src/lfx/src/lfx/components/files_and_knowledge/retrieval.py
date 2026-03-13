import json
import os
import uuid
from pathlib import Path
from typing import Any

import chromadb
import chromadb.api.client
from cryptography.fernet import InvalidToken
from langchain_chroma import Chroma
from langflow.services.auth.utils import decrypt_api_key
from langflow.services.database.models.user.crud import get_user_by_id
from pydantic import SecretStr

from lfx.base.knowledge_bases.knowledge_base_utils import get_knowledge_bases
from lfx.base.models.unified_models import (
    get_model_provider_variable_mapping,
    get_provider_all_variables,
)
from lfx.custom import Component
from lfx.io import BoolInput, DropdownInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.services.deps import get_settings_service, get_variable_service, session_scope
from lfx.utils.validate_cloud import raise_error_if_astra_cloud_disable_component

_KNOWLEDGE_BASES_ROOT_PATH: Path | None = None

# Error message to raise if we're in Astra cloud environment and the component is not supported.
astra_error_msg = "Knowledge retrieval is not supported in Astra cloud environment."


def _get_knowledge_bases_root_path() -> Path:
    """Lazy load the knowledge bases root path from settings."""
    global _KNOWLEDGE_BASES_ROOT_PATH  # noqa: PLW0603
    if _KNOWLEDGE_BASES_ROOT_PATH is None:
        settings = get_settings_service().settings
        knowledge_directory = settings.knowledge_bases_dir
        if not knowledge_directory:
            msg = "Knowledge bases directory is not set in the settings."
            raise ValueError(msg)
        _KNOWLEDGE_BASES_ROOT_PATH = Path(knowledge_directory).expanduser()
    return _KNOWLEDGE_BASES_ROOT_PATH


class KnowledgeBaseComponent(Component):
    display_name = "Knowledge Base"
    description = "Search and retrieve data from knowledge."
    icon = "download"
    name = "KnowledgeBase"

    inputs = [
        DropdownInput(
            name="knowledge_base",
            display_name="Knowledge",
            info="Select the knowledge to load data from.",
            required=True,
            options=[],
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
            tool_mode=True,
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
            info="Whether to include all metadata in the output. If false, only content is returned.",
            value=True,
            advanced=False,
        ),
        BoolInput(
            name="include_embeddings",
            display_name="Include Embeddings",
            info="Whether to include embeddings in the output. Only applicable if 'Include Metadata' is enabled.",
            value=False,
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            name="retrieve_data",
            display_name="Results",
            method="retrieve_data",
            info="Returns the data from the selected knowledge base.",
        ),
    ]

    async def update_build_config(self, build_config, field_value, field_name=None):  # noqa: ARG002
        # Check if we're in Astra cloud environment and raise an error if we are.
        raise_error_if_astra_cloud_disable_component(astra_error_msg)
        if field_name == "knowledge_base":
            # Update the knowledge base options dynamically
            build_config["knowledge_base"]["options"] = await get_knowledge_bases(
                _get_knowledge_bases_root_path(),
                user_id=self.user_id,  # Use the user_id from the component context
            )

            # If the selected knowledge base is not available, reset it
            if build_config["knowledge_base"]["value"] not in build_config["knowledge_base"]["options"]:
                build_config["knowledge_base"]["value"] = None

        return build_config

    @property
    def _user_uuid(self) -> uuid.UUID | None:
        """Return self.user_id as a UUID, converting from str if necessary."""
        if not self.user_id:
            return None
        return self.user_id if isinstance(self.user_id, uuid.UUID) else uuid.UUID(self.user_id)

    def _get_kb_metadata(self, kb_path: Path) -> dict:
        """Load and process knowledge base metadata."""
        # Check if we're in Astra cloud environment and raise an error if we are.
        raise_error_if_astra_cloud_disable_component(astra_error_msg)
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

    async def _resolve_provider_variables(self, provider: str) -> dict[str, str]:
        """Resolve all global variables for a provider using the async session.

        This avoids the run_until_complete thread dance by doing the lookup
        directly in the already-running async context.
        """
        result: dict[str, str] = {}
        provider_vars = get_provider_all_variables(provider)
        user_id = self._user_uuid
        if not provider_vars or not user_id:
            return result

        async with session_scope() as session:
            variable_service = get_variable_service()
            if variable_service is None:
                return result

            for var_info in provider_vars:
                var_key = var_info.get("variable_key")
                if not var_key:
                    continue
                try:
                    value = await variable_service.get_variable(
                        user_id=user_id,
                        name=var_key,
                        field="",
                        session=session,
                    )
                    if value and str(value).strip():
                        result[var_key] = str(value)
                except (ValueError, KeyError, AttributeError) as e:
                    logger.debug(f"Variable service lookup failed for '{var_key}', falling back to environment: {e}")
                    env_value = os.environ.get(var_key)
                    if env_value and env_value.strip():
                        result[var_key] = env_value
        return result

    async def _resolve_api_key(self, provider: str) -> str | None:
        """Resolve the API key for the given provider.

        Priority: user override > metadata (decrypted) > global variable.
        """
        provider_variable_map = get_model_provider_variable_mapping()
        variable_name = provider_variable_map.get(provider)
        user_id = self._user_uuid
        if not variable_name or not user_id:
            return None

        async with session_scope() as session:
            variable_service = get_variable_service()
            if variable_service is None:
                return None
            try:
                return await variable_service.get_variable(
                    user_id=user_id,
                    name=variable_name,
                    field="",
                    session=session,
                )
            except (ValueError, KeyError, AttributeError):
                return None

    def _build_embeddings(self, metadata: dict, *, api_key: str | None = None, provider_vars: dict | None = None):
        """Build embedding model from metadata.

        Args:
            metadata: The knowledge base embedding metadata.
            api_key: Pre-resolved API key (user override > metadata > global).
            provider_vars: Pre-resolved provider variables (for Ollama/WatsonX).
        """
        provider = metadata.get("embedding_provider")
        model = metadata.get("embedding_model")
        chunk_size = metadata.get("chunk_size")

        # Handle various providers
        if provider == "OpenAI":
            from langchain_openai import OpenAIEmbeddings

            if not api_key:
                msg = (
                    "OpenAI API key is required. Provide it in the component's advanced settings"
                    " or configure it globally."
                )
                raise ValueError(msg)
            openai_kwargs: dict = {"model": model, "api_key": api_key}
            if chunk_size is not None:
                openai_kwargs["chunk_size"] = chunk_size
            return OpenAIEmbeddings(**openai_kwargs)
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
        if provider == "Google Generative AI":
            from langchain_google_genai import GoogleGenerativeAIEmbeddings

            if not api_key:
                msg = (
                    "Google API key is required. Provide it in the component's advanced settings"
                    " or configure it globally."
                )
                raise ValueError(msg)
            return GoogleGenerativeAIEmbeddings(
                model=model,
                google_api_key=api_key,
            )
        if provider == "Ollama":
            from langchain_ollama import OllamaEmbeddings

            all_vars = provider_vars or {}
            base_url = all_vars.get("OLLAMA_BASE_URL")
            kwargs: dict = {"model": model}
            if base_url:
                kwargs["base_url"] = base_url
            return OllamaEmbeddings(**kwargs)
        if provider == "IBM WatsonX":
            from langchain_ibm import WatsonxEmbeddings

            all_vars = provider_vars or {}
            watsonx_apikey = api_key or all_vars.get("WATSONX_APIKEY")
            watsonx_project_id = all_vars.get("WATSONX_PROJECT_ID")
            watsonx_url = all_vars.get("WATSONX_URL")
            if not watsonx_apikey:
                msg = (
                    "IBM WatsonX API key is required. Provide it in the component's advanced settings"
                    " or configure it globally."
                )
                raise ValueError(msg)
            kwargs = {"model_id": model, "apikey": watsonx_apikey}
            if watsonx_project_id:
                kwargs["project_id"] = watsonx_project_id
            if watsonx_url:
                kwargs["url"] = watsonx_url
            return WatsonxEmbeddings(**kwargs)
        if provider == "Custom":
            # For custom embedding models, we would need additional configuration
            msg = "Custom embedding models not yet supported"
            raise NotImplementedError(msg)
        msg = f"Embedding provider '{provider}' is not supported for retrieval."
        raise NotImplementedError(msg)

    async def retrieve_data(self) -> DataFrame:
        """Retrieve data from the selected knowledge base by reading the Chroma collection.

        Returns:
            A DataFrame containing the data rows from the knowledge base.
        """
        # Check if we're in Astra cloud environment and raise an error if we are.
        raise_error_if_astra_cloud_disable_component(astra_error_msg)
        # Get the current user
        async with session_scope() as db:
            if not self.user_id:
                msg = "User ID is required for fetching Knowledge Base data."
                raise ValueError(msg)
            current_user = await get_user_by_id(db, self.user_id)
            if not current_user:
                msg = f"User with ID {self.user_id} not found."
                raise ValueError(msg)
            kb_user = current_user.username
        kb_path = _get_knowledge_bases_root_path() / kb_user / self.knowledge_base

        metadata = self._get_kb_metadata(kb_path)
        if not metadata:
            msg = f"Metadata not found for knowledge base: {self.knowledge_base}. Ensure it has been indexed."
            raise ValueError(msg)

        # Resolve API key: user override > metadata (decrypted) > global variable
        provider = metadata.get("embedding_provider")
        runtime_api_key = self.api_key.get_secret_value() if isinstance(self.api_key, SecretStr) else self.api_key
        api_key = runtime_api_key or metadata.get("api_key")
        if not api_key and provider:
            api_key = await self._resolve_api_key(provider)

        # Resolve provider-specific variables (e.g. base_url for Ollama, project_id for WatsonX)
        provider_vars: dict[str, str] = {}
        if provider in {"Ollama", "IBM WatsonX"}:
            provider_vars = await self._resolve_provider_variables(provider)

        # Build the embedder for the knowledge base
        embedding_function = self._build_embeddings(metadata, api_key=api_key, provider_vars=provider_vars)

        # Clear Chroma's singleton client cache to avoid "different settings"
        # conflicts when ingestion and retrieval run in the same process.
        chromadb.api.client.SharedSystemClient.clear_system_cache()
        chroma = Chroma(
            persist_directory=str(kb_path),
            embedding_function=embedding_function,
            collection_name=self.knowledge_base,
        )

        # If a search query is provided, perform a similarity search
        if self.search_query:
            # Use the search query to perform a similarity search
            logger.info("Performing similarity search")
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

        # If include_embeddings is enabled, get embeddings for the results
        id_to_embedding = {}
        if self.include_embeddings and results:
            doc_ids = [doc[0].metadata.get("_id") for doc in results if doc[0].metadata.get("_id")]

            # Only proceed if we have valid document IDs
            if doc_ids:
                # Access underlying collection to get embeddings
                collection = chroma._collection  # noqa: SLF001
                embeddings_result = collection.get(where={"_id": {"$in": doc_ids}}, include=["metadatas", "embeddings"])

                # Create a mapping from document ID to embedding
                for i, metadata in enumerate(embeddings_result.get("metadatas", [])):
                    if metadata and "_id" in metadata:
                        id_to_embedding[metadata["_id"]] = embeddings_result["embeddings"][i]

        # Build output data based on include_metadata setting
        data_list = []
        for doc in results:
            kwargs = {
                "content": doc[0].page_content,
            }
            if self.search_query:
                kwargs["_score"] = -1 * doc[1]
            if self.include_metadata:
                # Include all metadata, embeddings, and content
                kwargs.update(doc[0].metadata)
            if self.include_embeddings:
                kwargs["_embeddings"] = id_to_embedding.get(doc[0].metadata.get("_id"))

            data_list.append(Data(**kwargs))

        # Return the DataFrame containing the data
        return DataFrame(data=data_list)
