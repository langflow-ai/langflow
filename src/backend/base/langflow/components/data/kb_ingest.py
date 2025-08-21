from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from cryptography.fernet import InvalidToken
from langchain_chroma import Chroma
from loguru import logger

from langflow.base.models.openai_constants import OPENAI_EMBEDDING_MODEL_NAMES
from langflow.custom import Component
from langflow.io import BoolInput, DataFrameInput, DropdownInput, IntInput, Output, SecretStrInput, StrInput, TableInput
from langflow.schema.data import Data
from langflow.schema.dotdict import dotdict  # noqa: TC001
from langflow.schema.table import EditMode
from langflow.services.auth.utils import decrypt_api_key, encrypt_api_key
from langflow.services.deps import get_settings_service

HUGGINGFACE_MODEL_NAMES = ["sentence-transformers/all-MiniLM-L6-v2", "sentence-transformers/all-mpnet-base-v2"]
COHERE_MODEL_NAMES = ["embed-english-v3.0", "embed-multilingual-v3.0"]

settings = get_settings_service().settings
knowledge_directory = settings.knowledge_bases_dir
if not knowledge_directory:
    msg = "Knowledge bases directory is not set in the settings."
    raise ValueError(msg)
KNOWLEDGE_BASES_ROOT_PATH = Path(knowledge_directory).expanduser()


class KBIngestionComponent(Component):
    """Create or append to Langflow Knowledge from a DataFrame."""

    # ------ UI metadata ---------------------------------------------------
    display_name = "Knowledge Ingestion"
    description = "Create or update knowledge in Langflow."
    icon = "database"
    name = "KBIngestion"

    @dataclass
    class NewKnowledgeBaseInput:
        functionality: str = "create"
        fields: dict[str, dict] = field(
            default_factory=lambda: {
                "data": {
                    "node": {
                        "name": "create_knowledge_base",
                        "description": "Create new knowledge in Langflow.",
                        "display_name": "Create new knowledge",
                        "field_order": ["01_new_kb_name", "02_embedding_model", "03_api_key"],
                        "template": {
                            "01_new_kb_name": StrInput(
                                name="new_kb_name",
                                display_name="Knowledge Name",
                                info="Name of the new knowledge to create.",
                                required=True,
                            ),
                            "02_embedding_model": DropdownInput(
                                name="embedding_model",
                                display_name="Model Name",
                                info="Select the embedding model to use for this knowledge base.",
                                required=True,
                                options=OPENAI_EMBEDDING_MODEL_NAMES + HUGGINGFACE_MODEL_NAMES + COHERE_MODEL_NAMES,
                                options_metadata=[{"icon": "OpenAI"} for _ in OPENAI_EMBEDDING_MODEL_NAMES]
                                + [{"icon": "HuggingFace"} for _ in HUGGINGFACE_MODEL_NAMES]
                                + [{"icon": "Cohere"} for _ in COHERE_MODEL_NAMES],
                            ),
                            "03_api_key": SecretStrInput(
                                name="api_key",
                                display_name="API Key",
                                info="Provider API key for embedding model",
                                required=True,
                                load_from_db=True,
                            ),
                        },
                    },
                }
            }
        )

    # ------ Inputs --------------------------------------------------------
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
            dialog_inputs=asdict(NewKnowledgeBaseInput()),
        ),
        DataFrameInput(
            name="input_df",
            display_name="Data",
            info="Table with all original columns (already chunked / processed).",
            required=True,
        ),
        TableInput(
            name="column_config",
            display_name="Column Configuration",
            info="Configure column behavior for the knowledge base.",
            required=True,
            table_schema=[
                {
                    "name": "column_name",
                    "display_name": "Column Name",
                    "type": "str",
                    "description": "Name of the column in the source DataFrame",
                    "edit_mode": EditMode.INLINE,
                },
                {
                    "name": "vectorize",
                    "display_name": "Vectorize",
                    "type": "boolean",
                    "description": "Create embeddings for this column",
                    "default": False,
                    "edit_mode": EditMode.INLINE,
                },
                {
                    "name": "identifier",
                    "display_name": "Identifier",
                    "type": "boolean",
                    "description": "Use this column as unique identifier",
                    "default": False,
                    "edit_mode": EditMode.INLINE,
                },
            ],
            value=[
                {
                    "column_name": "text",
                    "vectorize": True,
                    "identifier": True,
                },
            ],
        ),
        IntInput(
            name="chunk_size",
            display_name="Chunk Size",
            info="Batch size for processing embeddings",
            advanced=True,
            value=1000,
        ),
        SecretStrInput(
            name="api_key",
            display_name="Embedding Provider API Key",
            info="API key for the embedding provider to generate embeddings.",
            advanced=True,
            required=False,
        ),
        BoolInput(
            name="allow_duplicates",
            display_name="Allow Duplicates",
            info="Allow duplicate rows in the knowledge base",
            advanced=True,
            value=False,
        ),
    ]

    # ------ Outputs -------------------------------------------------------
    outputs = [Output(display_name="DataFrame", name="dataframe", method="build_kb_info")]

    # ------ Internal helpers ---------------------------------------------
    def _get_kb_root(self) -> Path:
        """Return the root directory for knowledge bases."""
        return KNOWLEDGE_BASES_ROOT_PATH

    def _validate_column_config(self, df_source: pd.DataFrame) -> list[dict[str, Any]]:
        """Validate column configuration using Structured Output patterns."""
        if not self.column_config:
            msg = "Column configuration cannot be empty"
            raise ValueError(msg)

        # Convert table input to list of dicts (similar to Structured Output)
        config_list = self.column_config if isinstance(self.column_config, list) else []

        # Validate column names exist in DataFrame
        df_columns = set(df_source.columns)
        for config in config_list:
            col_name = config.get("column_name")
            if col_name not in df_columns:
                msg = f"Column '{col_name}' not found in DataFrame. Available columns: {sorted(df_columns)}"
                raise ValueError(msg)

        return config_list

    def _get_embedding_provider(self, embedding_model: str) -> str:
        """Get embedding provider by matching model name to lists."""
        if embedding_model in OPENAI_EMBEDDING_MODEL_NAMES:
            return "OpenAI"
        if embedding_model in HUGGINGFACE_MODEL_NAMES:
            return "HuggingFace"
        if embedding_model in COHERE_MODEL_NAMES:
            return "Cohere"
        return "Custom"

    def _build_embeddings(self, embedding_model: str, api_key: str):
        """Build embedding model using provider patterns."""
        # Get provider by matching model name to lists
        provider = self._get_embedding_provider(embedding_model)

        # Validate provider and model
        if provider == "OpenAI":
            from langchain_openai import OpenAIEmbeddings

            if not api_key:
                msg = "OpenAI API key is required when using OpenAI provider"
                raise ValueError(msg)
            return OpenAIEmbeddings(
                model=embedding_model,
                api_key=api_key,
                chunk_size=self.chunk_size,
            )
        if provider == "HuggingFace":
            from langchain_huggingface import HuggingFaceEmbeddings

            return HuggingFaceEmbeddings(
                model=embedding_model,
            )
        if provider == "Cohere":
            from langchain_cohere import CohereEmbeddings

            if not api_key:
                msg = "Cohere API key is required when using Cohere provider"
                raise ValueError(msg)
            return CohereEmbeddings(
                model=embedding_model,
                cohere_api_key=api_key,
            )
        if provider == "Custom":
            # For custom embedding models, we would need additional configuration
            msg = "Custom embedding models not yet supported"
            raise NotImplementedError(msg)
        msg = f"Unknown provider: {provider}"
        raise ValueError(msg)

    def _build_embedding_metadata(self, embedding_model, api_key) -> dict[str, Any]:
        """Build embedding model metadata."""
        # Get provider by matching model name to lists
        embedding_provider = self._get_embedding_provider(embedding_model)

        api_key_to_save = None
        if api_key and hasattr(api_key, "get_secret_value"):
            api_key_to_save = api_key.get_secret_value()
        elif isinstance(api_key, str):
            api_key_to_save = api_key

        encrypted_api_key = None
        if api_key_to_save:
            settings_service = get_settings_service()
            try:
                encrypted_api_key = encrypt_api_key(api_key_to_save, settings_service=settings_service)
            except (TypeError, ValueError) as e:
                self.log(f"Could not encrypt API key: {e}")
                logger.error(f"Could not encrypt API key: {e}")

        return {
            "embedding_provider": embedding_provider,
            "embedding_model": embedding_model,
            "api_key": encrypted_api_key,
            "api_key_used": bool(api_key),
            "chunk_size": self.chunk_size,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def _save_embedding_metadata(self, kb_path: Path, embedding_model: str, api_key: str) -> None:
        """Save embedding model metadata."""
        embedding_metadata = self._build_embedding_metadata(embedding_model, api_key)
        metadata_path = kb_path / "embedding_metadata.json"
        metadata_path.write_text(json.dumps(embedding_metadata, indent=2))

    def _save_kb_files(
        self,
        kb_path: Path,
        config_list: list[dict[str, Any]],
    ) -> None:
        """Save KB files using File Component storage patterns."""
        try:
            # Create directory (following File Component patterns)
            kb_path.mkdir(parents=True, exist_ok=True)

            # Save column configuration
            # Only do this if the file doesn't exist already
            cfg_path = kb_path / "schema.json"
            if not cfg_path.exists():
                cfg_path.write_text(json.dumps(config_list, indent=2))

        except (OSError, TypeError, ValueError) as e:
            self.log(f"Error saving KB files: {e}")

    def _build_column_metadata(self, config_list: list[dict[str, Any]], df_source: pd.DataFrame) -> dict[str, Any]:
        """Build detailed column metadata."""
        metadata: dict[str, Any] = {
            "total_columns": len(df_source.columns),
            "mapped_columns": len(config_list),
            "unmapped_columns": len(df_source.columns) - len(config_list),
            "columns": [],
            "summary": {"vectorized_columns": [], "identifier_columns": []},
        }

        for config in config_list:
            col_name = config.get("column_name")
            vectorize = config.get("vectorize") == "True" or config.get("vectorize") is True
            identifier = config.get("identifier") == "True" or config.get("identifier") is True

            # Add to columns list
            metadata["columns"].append(
                {
                    "name": col_name,
                    "vectorize": vectorize,
                    "identifier": identifier,
                }
            )

            # Update summary
            if vectorize:
                metadata["summary"]["vectorized_columns"].append(col_name)
            if identifier:
                metadata["summary"]["identifier_columns"].append(col_name)

        return metadata

    def _create_vector_store(
        self, df_source: pd.DataFrame, config_list: list[dict[str, Any]], embedding_model: str, api_key: str
    ) -> None:
        """Create vector store following Local DB component pattern."""
        try:
            # Set up vector store directory
            base_dir = self._get_kb_root()

            vector_store_dir = base_dir / self.knowledge_base
            vector_store_dir.mkdir(parents=True, exist_ok=True)

            # Create embeddings model
            embedding_function = self._build_embeddings(embedding_model, api_key)

            # Convert DataFrame to Data objects (following Local DB pattern)
            data_objects = self._convert_df_to_data_objects(df_source, config_list)

            # Create vector store
            chroma = Chroma(
                persist_directory=str(vector_store_dir),
                embedding_function=embedding_function,
                collection_name=self.knowledge_base,
            )

            # Convert Data objects to LangChain Documents
            documents = []
            for data_obj in data_objects:
                doc = data_obj.to_lc_document()
                documents.append(doc)

            # Add documents to vector store
            if documents:
                chroma.add_documents(documents)
                self.log(f"Added {len(documents)} documents to vector store '{self.knowledge_base}'")

        except (OSError, ValueError, RuntimeError) as e:
            self.log(f"Error creating vector store: {e}")

    def _convert_df_to_data_objects(self, df_source: pd.DataFrame, config_list: list[dict[str, Any]]) -> list[Data]:
        """Convert DataFrame to Data objects for vector store."""
        data_objects: list[Data] = []

        # Set up vector store directory
        base_dir = self._get_kb_root()

        # If we don't allow duplicates, we need to get the existing hashes
        chroma = Chroma(
            persist_directory=str(base_dir / self.knowledge_base),
            collection_name=self.knowledge_base,
        )

        # Get all documents and their metadata
        all_docs = chroma.get()

        # Extract all _id values from metadata
        id_list = [metadata.get("_id") for metadata in all_docs["metadatas"] if metadata.get("_id")]

        # Get column roles
        content_cols = []
        identifier_cols = []

        for config in config_list:
            col_name = config.get("column_name")
            vectorize = config.get("vectorize") == "True" or config.get("vectorize") is True
            identifier = config.get("identifier") == "True" or config.get("identifier") is True

            if vectorize:
                content_cols.append(col_name)
            elif identifier:
                identifier_cols.append(col_name)

        # Convert each row to a Data object
        for _, row in df_source.iterrows():
            # Build content text from identifier columns using list comprehension
            identifier_parts = [str(row[col]) for col in content_cols if col in row and pd.notna(row[col])]

            # Join all parts into a single string
            page_content = " ".join(identifier_parts)

            # Build metadata from NON-vectorized columns only (simple key-value pairs)
            data_dict = {
                "text": page_content,  # Main content for vectorization
            }

            # Add identifier columns if they exist
            if identifier_cols:
                identifier_parts = [str(row[col]) for col in identifier_cols if col in row and pd.notna(row[col])]
                page_content = " ".join(identifier_parts)

            # Add metadata columns as simple key-value pairs
            for col in df_source.columns:
                if col not in content_cols and col in row and pd.notna(row[col]):
                    # Convert to simple types for Chroma metadata
                    value = row[col]
                    data_dict[col] = str(value)  # Convert complex types to string

            # Hash the page_content for unique ID
            page_content_hash = hashlib.sha256(page_content.encode()).hexdigest()
            data_dict["_id"] = page_content_hash

            # If duplicates are disallowed, and hash exists, prevent adding this row
            if not self.allow_duplicates and page_content_hash in id_list:
                self.log(f"Skipping duplicate row with hash {page_content_hash}")
                continue

            # Create Data object - everything except "text" becomes metadata
            data_obj = Data(data=data_dict)
            data_objects.append(data_obj)

        return data_objects

    def is_valid_collection_name(self, name, min_length: int = 3, max_length: int = 63) -> bool:
        """Validates collection name against conditions 1-3.

        1. Contains 3-63 characters
        2. Starts and ends with alphanumeric character
        3. Contains only alphanumeric characters, underscores, or hyphens.

        Args:
            name (str): Collection name to validate
            min_length (int): Minimum length of the name
            max_length (int): Maximum length of the name

        Returns:
            bool: True if valid, False otherwise
        """
        # Check length (condition 1)
        if not (min_length <= len(name) <= max_length):
            return False

        # Check start/end with alphanumeric (condition 2)
        if not (name[0].isalnum() and name[-1].isalnum()):
            return False

        # Check allowed characters (condition 3)
        return re.match(r"^[a-zA-Z0-9_-]+$", name) is not None

    # ---------------------------------------------------------------------
    #                         OUTPUT METHODS
    # ---------------------------------------------------------------------
    def build_kb_info(self) -> Data:
        """Main ingestion routine → returns a dict with KB metadata."""
        try:
            # Get source DataFrame
            df_source: pd.DataFrame = self.input_df

            # Validate column configuration (using Structured Output patterns)
            config_list = self._validate_column_config(df_source)
            column_metadata = self._build_column_metadata(config_list, df_source)

            # Prepare KB folder (using File Component patterns)
            kb_root = self._get_kb_root()
            kb_path = kb_root / self.knowledge_base

            # Read the embedding info from the knowledge base folder
            metadata_path = kb_path / "embedding_metadata.json"

            # If the API key is not provided, try to read it from the metadata file
            if metadata_path.exists():
                settings_service = get_settings_service()
                metadata = json.loads(metadata_path.read_text())
                embedding_model = metadata.get("embedding_model")
                try:
                    api_key = decrypt_api_key(metadata["api_key"], settings_service)
                except (InvalidToken, TypeError, ValueError) as e:
                    logger.error(f"Could not decrypt API key. Please provide it manually. Error: {e}")

            # Check if a custom API key was provided, update metadata if so
            if self.api_key:
                api_key = self.api_key
                self._save_embedding_metadata(
                    kb_path=kb_path,
                    embedding_model=embedding_model,
                    api_key=api_key,
                )

            # Create vector store following Local DB component pattern
            self._create_vector_store(df_source, config_list, embedding_model=embedding_model, api_key=api_key)

            # Save KB files (using File Component storage patterns)
            self._save_kb_files(kb_path, config_list)

            # Build metadata response
            meta: dict[str, Any] = {
                "kb_id": str(uuid.uuid4()),
                "kb_name": self.knowledge_base,
                "rows": len(df_source),
                "column_metadata": column_metadata,
                "path": str(kb_path),
                "config_columns": len(config_list),
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            }

            # Set status message
            self.status = f"✅ KB **{self.knowledge_base}** saved · {len(df_source)} chunks."

            return Data(data=meta)

        except (OSError, ValueError, RuntimeError, KeyError) as e:
            self.log(f"Error in KB ingestion: {e}")
            self.status = f"❌ KB ingestion failed: {e}"
            return Data(data={"error": str(e), "kb_name": self.knowledge_base})

    def _get_knowledge_bases(self) -> list[str]:
        """Retrieve a list of available knowledge bases.

        Returns:
            A list of knowledge base names.
        """
        # Return the list of directories in the knowledge base root path
        kb_root_path = self._get_kb_root()

        if not kb_root_path.exists():
            return []

        return [str(d.name) for d in kb_root_path.iterdir() if not d.name.startswith(".") and d.is_dir()]

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None) -> dotdict:
        """Update build configuration based on provider selection."""
        # Create a new knowledge base
        if field_name == "knowledge_base":
            if isinstance(field_value, dict) and "01_new_kb_name" in field_value:
                # Validate the knowledge base name - Make sure it follows these rules:
                if not self.is_valid_collection_name(field_value["01_new_kb_name"]):
                    msg = f"Invalid knowledge base name: {field_value['01_new_kb_name']}"
                    raise ValueError(msg)

                # We need to test the API Key one time against the embedding model
                embed_model = self._build_embeddings(
                    embedding_model=field_value["02_embedding_model"], api_key=field_value["03_api_key"]
                )

                # Try to generate a dummy embedding to validate the API key
                embed_model.embed_query("test")

                # Create the new knowledge base directory
                kb_path = KNOWLEDGE_BASES_ROOT_PATH / field_value["01_new_kb_name"]
                kb_path.mkdir(parents=True, exist_ok=True)

                # Save the embedding metadata
                build_config["knowledge_base"]["value"] = field_value["01_new_kb_name"]
                self._save_embedding_metadata(
                    kb_path=kb_path,
                    embedding_model=field_value["02_embedding_model"],
                    api_key=field_value["03_api_key"],
                )

            # Update the knowledge base options dynamically
            build_config["knowledge_base"]["options"] = self._get_knowledge_bases()
            if build_config["knowledge_base"]["value"] not in build_config["knowledge_base"]["options"]:
                build_config["knowledge_base"]["value"] = None

        return build_config
