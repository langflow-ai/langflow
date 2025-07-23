from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from cryptography.fernet import InvalidToken
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from loguru import logger
from platformdirs import user_cache_dir

from langflow.base.models.openai_constants import OPENAI_EMBEDDING_MODEL_NAMES
from langflow.custom import Component
from langflow.io import (
    BoolInput,
    DataFrameInput,
    DropdownInput,
    IntInput,
    Output,
    SecretStrInput,
    StrInput,
    TableInput,
)
from langflow.schema import Message
from langflow.schema.data import Data
from langflow.schema.dotdict import dotdict  # noqa: TC001
from langflow.schema.table import EditMode
from langflow.services.auth.utils import decrypt_api_key, encrypt_api_key
from langflow.services.deps import get_settings_service

HUGGINGFACE_MODEL_NAMES = ["sentence-transformers/all-MiniLM-L6-v2", "sentence-transformers/all-mpnet-base-v2"]
COHERE_MODEL_NAMES = ["embed-english-v3.0", "embed-multilingual-v3.0"]

KNOWLEDGE_BASES_DIR = "~/.langflow/knowledge_bases"
KNOWLEDGE_BASES_ROOT_PATH = Path(KNOWLEDGE_BASES_DIR).expanduser()


class KBIngestionComponent(Component):
    """Create or append to a Langflow Knowledge Base from a DataFrame."""

    # ------ UI metadata ---------------------------------------------------
    display_name = "Ingest Knowledge"
    description = "Create or append to a Langflow Knowledge Base from a DataFrame."
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
                        "description": "Create a new knowledge base in Langflow.",
                        "display_name": "Create new knowledge base",
                        "field_order": ["01_new_kb_name", "02_embedding_model", "03_api_key"],
                        "template": {
                            "01_new_kb_name": StrInput(
                                name="new_kb_name",
                                display_name="Knowledge Base Name",
                                info="Name of the new knowledge base to create.",
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
            display_name="Knowledge Base",
            info="Select the knowledge base to load files from.",
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
                    "identifier": False,
                }
            ],
        ),
        IntInput(
            name="chunk_size",
            display_name="Chunk Size",
            info="Batch size for processing embeddings",
            advanced=True,
            value=1000,
        ),
        StrInput(
            name="kb_root_path",
            display_name="KB Root Path",
            info="Root directory for knowledge bases (defaults to ~/.langflow/knowledge_bases)",
            advanced=True,
            value=KNOWLEDGE_BASES_DIR,
        ),
        SecretStrInput(
            name="api_key",
            display_name="Embedding Provider API Key",
            info="API key for the embedding provider to generate embeddings.",
            advanced=True,
            required=False,
        ),
        BoolInput(
            name="silent_errors",
            display_name="Silent Errors",
            info="Continue processing even if some operations fail",
            advanced=True,
            value=False,
        ),
    ]

    # ------ Outputs -------------------------------------------------------
    outputs = [
        Output(
            name="kb_info",
            display_name="Info",
            method="build_kb_info",
            info="Returns basic metadata of the newly ingested KB.",
        ),
    ]

    # ------ Internal helpers ---------------------------------------------
    def _get_kb_root(self) -> Path:
        """Get KB root path with File Component pattern."""
        if self.kb_root_path:
            return Path(self._resolve_path(self.kb_root_path))
        return Path.home() / ".langflow" / "knowledge_bases"

    def _resolve_path(self, path: str) -> str:
        """Resolves the path to an absolute path."""
        if not path:
            return path
        path_object = Path(path)

        if path_object.parts and path_object.parts[0] == "~":
            path_object = path_object.expanduser()
        elif path_object.is_relative_to("."):
            path_object = path_object.resolve()
        return str(path_object)

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
                if not self.silent_errors:
                    raise ValueError(msg)
                self.log(f"Warning: {msg}")

        return config_list

    def _build_embeddings(self, embedding_model: str, api_key: str):
        """Build embedding model using provider patterns."""
        # Get provider by matching model name to lists
        provider = (
            "OpenAI"
            if embedding_model in OPENAI_EMBEDDING_MODEL_NAMES
            else "HuggingFace"
            if embedding_model in HUGGINGFACE_MODEL_NAMES
            else "Cohere"
        )
        chunk_size = self.chunk_size

        # TODO: Support all embedding providers
        if provider == "OpenAI":
            if not api_key:
                msg = "OpenAI API key is required when using OpenAI provider"
                raise ValueError(msg)
            return OpenAIEmbeddings(
                model=embedding_model,
                api_key=api_key,
                chunk_size=chunk_size,
            )
        if provider == "Custom":
            # For custom embedding models, we would need additional configuration
            msg = "Custom embedding models not yet supported"
            raise NotImplementedError(msg)
        msg = f"Unknown provider: {provider}"
        raise ValueError(msg)

    def _process_embeddings(
        self,
        df_source: pd.DataFrame,
        config_list: list[dict[str, Any]],
        embedding_model: str,
        api_key: str,
    ) -> tuple[np.ndarray, list[str]]:
        """Process embeddings using Embedding Model Component patterns."""
        # Find columns marked for vectorization
        vector_cols = []
        for config in config_list:
            col_name = config.get("column_name")
            vectorize = config.get("vectorize") == "True" or config.get("vectorize") is True

            # Include in embedding if specifically marked for vectorization
            if vectorize:
                vector_cols.append(col_name)

        if not vector_cols:
            self.status = "⚠️ No columns marked for vectorization - skipping embedding."
            return np.empty((0, 0)), []

        # Filter valid columns
        valid_cols = [col for col in vector_cols if col in df_source.columns]
        if not valid_cols:
            if not self.silent_errors:
                msg = f"No valid columns found for embedding. Requested: {vector_cols}"
                raise ValueError(msg)
            self.log("Warning: No valid columns for embedding")
            return np.empty((0, 0)), []

        # Combine text from multiple columns
        texts: list[str] = [
            " | ".join([str(row[col]) for col in valid_cols if pd.notna(row[col])])
            if any(pd.notna(row[col]) for col in valid_cols)
            else ""
            for _, row in df_source.iterrows()
        ]

        # Generate embeddings using the model (following Embedding Model patterns)
        try:
            embedder = self._build_embeddings(embedding_model, api_key)
            if hasattr(embedder, "embed_documents"):
                embeddings = np.array(embedder.embed_documents(texts))
            elif hasattr(embedder, "embed"):
                embeddings = np.array([embedder.embed(t) for t in texts])
            else:
                msg = "Embedding Model must expose `.embed_documents(list[str])` or `.embed(str)`."
                raise AttributeError(msg)

            embed_index = [str(uuid.uuid4()) for _ in texts]
        except Exception as e:
            if not self.silent_errors:
                raise
            self.log(f"Error generating embeddings: {e}")
            return np.empty((0, 0)), []
        else:
            return embeddings, embed_index

    def _build_embedding_metadata(self, embedding_model, api_key) -> dict[str, Any]:
        """Build embedding model metadata."""
        # Get provider by matching model name to lists
        embedding_provider = (
            "OpenAI"
            if embedding_model in OPENAI_EMBEDDING_MODEL_NAMES
            else "HuggingFace"
            if embedding_model in HUGGINGFACE_MODEL_NAMES
            else "Cohere"
        )

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
        df_source: pd.DataFrame,
        config_list: list[dict[str, Any]],
    ) -> None:
        """Save KB files using File Component storage patterns."""
        try:
            # Create directory (following File Component patterns)
            kb_path.mkdir(parents=True, exist_ok=True)

            # Save updated DataFrame
            df_path = kb_path / "source.parquet"
            df_source.to_parquet(df_path, index=False)

            # Save column configuration
            # Only do this if the file doesn't exist already
            cfg_path = kb_path / "schema.json"
            if not cfg_path.exists():
                cfg_path.write_text(json.dumps(config_list, indent=2))

        except Exception as e:
            if not self.silent_errors:
                raise
            self.log(f"Error saving KB files: {e}")

    def _calculate_text_stats(self, df_source: pd.DataFrame, config_list: list[dict[str, Any]]) -> dict[str, int]:
        """Calculate word and character counts for text columns."""
        total_words = 0
        total_chars = 0

        for config in config_list:
            col_name = config.get("column_name")

            # Only count text-based columns
            if col_name in df_source.columns:
                col_data = df_source[col_name].astype(str).fillna("")

                # Count characters
                total_chars += col_data.str.len().sum()

                # Count words (split by whitespace)
                total_words += col_data.str.split().str.len().fillna(0).sum()

        return {"word_count": int(total_words), "char_count": int(total_chars)}

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
            # Set up vector store directory (following Local DB pattern)
            if self.kb_root_path:
                base_dir = Path(self._resolve_path(self.kb_root_path))
            else:
                base_dir = Path(user_cache_dir("langflow", "langflow"))

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

        except Exception as e:
            if not self.silent_errors:
                raise
            self.log(f"Error creating vector store: {e}")

    def _convert_df_to_data_objects(self, df_source: pd.DataFrame, config_list: list[dict[str, Any]]) -> list[Data]:
        """Convert DataFrame to Data objects for vector store."""
        data_objects = []

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
            # Build content text from vectorized columns using list comprehension
            content_parts = [str(row[col]) for col in content_cols if col in row and pd.notna(row[col])]

            page_content = " ".join(content_parts)

            # Build metadata from NON-vectorized columns only (simple key-value pairs)
            data_dict = {
                "text": page_content,  # Main content for vectorization
            }

            # Add metadata columns as simple key-value pairs
            for col in df_source.columns:
                if col not in content_cols and col in row and pd.notna(row[col]):
                    # Convert to simple types for Chroma metadata
                    value = row[col]
                    if isinstance(value, str | int | float | bool):
                        data_dict[col] = str(value)
                    else:
                        data_dict[col] = str(value)  # Convert complex types to string

            # Hash the page_content for unique ID
            page_content_hash = hashlib.sha256(page_content.encode()).hexdigest()
            data_dict["_id"] = page_content_hash

            # TODO: If duplicates are disallowed, and hash exists, prevent adding this row

            # Create Data object - everything except "text" becomes metadata
            data_obj = Data(data=data_dict)
            data_objects.append(data_obj)

        return data_objects

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

            # Prepare KB folder (using File Component patterns)
            kb_root = self._get_kb_root()
            kb_path = kb_root / self.knowledge_base

            # Save source DataFrame
            df_path = kb_path / "source.parquet"

            # Instead of just overwriting this file, i want to read it and append to it if it exists
            df_source_combined = df_source.copy()
            if df_path.exists():
                # Read existing DataFrame
                existing_df = pd.read_parquet(df_path)
                # Append new data
                df_source_combined = pd.concat([existing_df, df_source_combined], ignore_index=True)

            # Read the embedding info from the knowledge base folder
            metadata_path = kb_path / "embedding_metadata.json"
            api_key = self.api_key or ""
            if not api_key and metadata_path.exists():
                settings_service = get_settings_service()
                metadata = json.loads(metadata_path.read_text())
                embedding_model = metadata.get("embedding_model")
            try:
                api_key = decrypt_api_key(metadata["api_key"], settings_service)
            except (InvalidToken, TypeError, ValueError) as e:
                logger.error(f"Could not decrypt API key. Please provide it manually. Error: {e}")

            # Process embeddings (using Embedding Model patterns)
            embeddings, embed_index = self._process_embeddings(
                df_source,
                config_list,
                embedding_model=embedding_model,
                api_key=api_key,
            )

            # Create vector store following Local DB component pattern
            self._create_vector_store(df_source, config_list, embedding_model=embedding_model, api_key=api_key)

            # Save KB files (using File Component storage patterns)
            self._save_kb_files(kb_path, df_source_combined, config_list)

            # Calculate text statistics
            text_stats = self._calculate_text_stats(df_source_combined, config_list)

            # Build metadata response
            meta: dict[str, Any] = {
                "kb_id": str(uuid.uuid4()),
                "kb_name": self.knowledge_base,
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                "rows": len(df_source),
                "vectorised_rows": len(embeddings) if embeddings.size > 0 else 0,
                "vector_dim": int(embeddings.shape[1]) if embeddings.size > 0 else 0,
                "word_count": text_stats["word_count"],
                "char_count": text_stats["char_count"],
                "column_metadata": self._build_column_metadata(config_list, df_source),
                "created_or_updated": True,
                "path": str(kb_path),
                "config_columns": len(config_list),
            }

            # Set status message
            vector_count = len(embeddings) if embeddings.size > 0 else 0
            self.status = f"✅ KB **{self.knowledge_base}** saved · {len(df_source)} rows, {vector_count} embedded."

            return Data(data=meta)

        except Exception as e:
            if not self.silent_errors:
                raise
            self.log(f"Error in KB ingestion: {e}")
            self.status = f"❌ KB ingestion failed: {e}"
            return Data(data={"error": str(e), "kb_name": self.knowledge_base})

    def status_message(self) -> Message:
        """Return the human-readable status string."""
        return Message(text=self.status or "KB ingestion completed.")

    def _get_knowledge_bases(self) -> list[str]:
        """Retrieve a list of available knowledge bases.

        Returns:
            A list of knowledge base names.
        """
        # Return the list of directories in the knowledge base root path
        kb_root_path = Path(self.kb_root_path).expanduser()

        if not kb_root_path.exists():
            return []

        return [str(d.name) for d in kb_root_path.iterdir() if not d.name.startswith(".") and d.is_dir()]

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None) -> dotdict:
        """Update build configuration based on provider selection."""
        # Create a new knowledge base
        if field_name == "knowledge_base":
            if isinstance(field_value, dict) and "01_new_kb_name" in field_value:
                kb_path = Path(KNOWLEDGE_BASES_ROOT_PATH, field_value["01_new_kb_name"]).expanduser()
                kb_path.mkdir(parents=True, exist_ok=True)

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
