from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from langchain_chroma import Chroma
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


class KBIngestionComponent(Component):
    """Create or append to a Langflow Knowledge Base from a DataFrame."""

    # ------ UI metadata ---------------------------------------------------
    display_name = "Build KB"
    description = (
        "Takes a DataFrame, a column-level config table, and an Embedding Model handle, "
        "then writes a fully-formed Knowledge Base folder ready for retrieval."
    )
    icon = "folder"
    name = "KBIngestion"

    # ------ Inputs --------------------------------------------------------
    inputs = [
        DataFrameInput(
            name="input_df",
            display_name="Source DataFrame",
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
                    "name": "data_type",
                    "display_name": "Data Type",
                    "type": "str",
                    "description": "Data type for proper indexing and filtering",
                    "options": ["string", "number", "boolean", "date", "json"],
                    "default": "string",
                    "edit_mode": EditMode.INLINE,
                },
                {
                    "name": "vectorize",
                    "display_name": "Vectorize",
                    "type": "boolean",
                    "description": "Create embeddings for this column",
                    "default": "False",
                    "edit_mode": EditMode.INLINE,
                },
                {
                    "name": "citation",
                    "display_name": "Citation",
                    "type": "boolean",
                    "description": "Use this column for citation/reference",
                    "default": "False",
                    "edit_mode": EditMode.INLINE,
                },
                {
                    "name": "identifier",
                    "display_name": "Identifier",
                    "type": "boolean",
                    "description": "Use this column as unique identifier",
                    "default": "False",
                    "edit_mode": EditMode.INLINE,
                },
            ],
            value=[
                {
                    "column_name": "content",
                    "data_type": "string",
                    "vectorize": "True",
                    "citation": "False",
                    "identifier": "False",
                }
            ],
        ),
        DropdownInput(
            name="embedding_provider",
            display_name="Embedding Provider",
            options=["OpenAI", "HuggingFace", "Cohere", "Custom"],
            value="OpenAI",
            info="Select the embedding model provider",
            real_time_refresh=True,
        ),
        DropdownInput(
            name="embedding_model",
            display_name="Model Name",
            options=["text-embedding-3-small", "text-embedding-3-large", "text-embedding-ada-002"],
            value="text-embedding-3-small",
            info="Select the embedding model to use",
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="Provider API key for embedding model",
            required=True,
        ),
        IntInput(
            name="dimensions",
            display_name="Dimensions",
            info="Number of dimensions for embeddings (if supported)",
            advanced=True,
        ),
        IntInput(
            name="chunk_size",
            display_name="Chunk Size",
            info="Batch size for processing embeddings",
            advanced=True,
            value=1000,
        ),
        StrInput(
            name="kb_name",
            display_name="KB Name",
            info="New or existing KB folder name (ASCII & dashes only).",
            required=True,
        ),
        StrInput(
            name="kb_root_path",
            display_name="KB Root Path",
            info="Root directory for knowledge bases (defaults to ~/.langflow/knowledge_bases)",
            advanced=True,
        ),
        StrInput(
            name="collection_name",
            display_name="Collection Name",
            info="Name for the vector store collection (defaults to KB name)",
            advanced=True,
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
            display_name="KB Info",
            method="build_kb_info",
            info="Returns basic metadata of the newly ingested KB.",
        ),
        Output(
            name="status_msg",
            display_name="Status",
            method="status_message",
            info="Short human-readable summary.",
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

    def _build_embeddings(self):
        """Build embedding model using provider patterns."""
        from langchain_openai import OpenAIEmbeddings

        provider = self.embedding_provider
        model = self.embedding_model
        api_key = self.api_key
        dimensions = self.dimensions
        chunk_size = self.chunk_size

        if provider == "OpenAI":
            if not api_key:
                msg = "OpenAI API key is required when using OpenAI provider"
                raise ValueError(msg)
            return OpenAIEmbeddings(
                model=model,
                dimensions=dimensions or None,
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
        texts: list[str] = df_source[valid_cols].astype(str).agg(" ".join, axis=1).tolist()

        # Generate embeddings using the model (following Embedding Model patterns)
        try:
            embedder = self._build_embeddings()
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

    def _save_kb_files(
        self,
        kb_path: Path,
        df_source: pd.DataFrame,
        config_list: list[dict[str, Any]],
        embeddings: np.ndarray,
        embed_index: list[str],
    ) -> None:
        """Save KB files using File Component storage patterns."""
        try:
            # Create directory (following File Component patterns)
            kb_path.mkdir(parents=True, exist_ok=True)

            # Save source DataFrame
            df_path = kb_path / "source.parquet"
            df_source.to_parquet(df_path, index=False)

            # Save column configuration
            cfg_path = kb_path / "schema.json"
            cfg_path.write_text(json.dumps(config_list, indent=2))

            # Save embeddings and IDs if available
            if embeddings.size > 0:
                np.save(kb_path / "vectors.npy", embeddings)
                (kb_path / "ids.json").write_text(json.dumps(embed_index))

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
            data_type = config.get("data_type", "string")

            # Only count text-based columns
            if data_type == "string" and col_name in df_source.columns:
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
            "summary": {"vectorized_columns": [], "citation_columns": [], "identifier_columns": [], "data_types": {}},
        }

        for config in config_list:
            col_name = config.get("column_name")
            data_type = config.get("data_type", "string")
            vectorize = config.get("vectorize") == "True" or config.get("vectorize") is True
            citation = config.get("citation") == "True" or config.get("citation") is True
            identifier = config.get("identifier") == "True" or config.get("identifier") is True

            # Add to columns list
            metadata["columns"].append(
                {
                    "name": col_name,
                    "data_type": data_type,
                    "vectorize": vectorize,
                    "citation": citation,
                    "identifier": identifier,
                }
            )

            # Update summary
            if vectorize:
                metadata["summary"]["vectorized_columns"].append(col_name)
            if citation:
                metadata["summary"]["citation_columns"].append(col_name)
            if identifier:
                metadata["summary"]["identifier_columns"].append(col_name)

            # Count data types
            if data_type not in metadata["summary"]["data_types"]:
                metadata["summary"]["data_types"][data_type] = 0
            metadata["summary"]["data_types"][data_type] += 1

        return metadata

    def _create_vector_store(self, df_source: pd.DataFrame, config_list: list[dict[str, Any]]) -> None:
        """Create vector store following Local DB component pattern."""
        try:
            # Get collection name (default to KB name)
            collection_name = self.collection_name if self.collection_name else self.kb_name

            # Set up vector store directory (following Local DB pattern)
            if self.kb_root_path:
                base_dir = Path(self._resolve_path(self.kb_root_path))
            else:
                base_dir = Path(user_cache_dir("langflow", "langflow"))

            vector_store_dir = base_dir / "vector_stores" / collection_name
            vector_store_dir.mkdir(parents=True, exist_ok=True)

            # Create embeddings model
            embedding_function = self._build_embeddings()

            # Convert DataFrame to Data objects (following Local DB pattern)
            data_objects = self._convert_df_to_data_objects(df_source, config_list)

            # Create vector store
            chroma = Chroma(
                persist_directory=str(vector_store_dir),
                embedding_function=embedding_function,
                collection_name=collection_name,
            )

            # Convert Data objects to LangChain Documents
            documents = []
            for data_obj in data_objects:
                doc = data_obj.to_lc_document()
                documents.append(doc)

            # Add documents to vector store
            if documents:
                chroma.add_documents(documents)
                self.log(f"Added {len(documents)} documents to vector store '{collection_name}'")

        except Exception as e:
            if not self.silent_errors:
                raise
            self.log(f"Error creating vector store: {e}")

    def _convert_df_to_data_objects(self, df_source: pd.DataFrame, config_list: list[dict[str, Any]]) -> list[Data]:
        """Convert DataFrame to Data objects for vector store."""
        data_objects = []

        # Get column roles
        content_cols = []
        citation_cols = []
        identifier_cols = []

        for config in config_list:
            col_name = config.get("column_name")
            vectorize = config.get("vectorize") == "True" or config.get("vectorize") is True
            citation = config.get("citation") == "True" or config.get("citation") is True
            identifier = config.get("identifier") == "True" or config.get("identifier") is True

            if vectorize:
                content_cols.append(col_name)
            elif citation:
                citation_cols.append(col_name)
            elif identifier:
                identifier_cols.append(col_name)

        # Convert each row to a Data object
        for idx, row in df_source.iterrows():
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

            # Add special metadata flags
            data_dict["_row_index"] = str(idx)
            data_dict["_kb_name"] = str(self.kb_name)

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
            kb_path = kb_root / self.kb_name

            # Process embeddings (using Embedding Model patterns)
            embeddings, embed_index = self._process_embeddings(df_source, config_list)

            # Save KB files (using File Component storage patterns)
            self._save_kb_files(kb_path, df_source, config_list, embeddings, embed_index)

            # Create vector store following Local DB component pattern
            self._create_vector_store(df_source, config_list)  # TODO: Restore  embeddings, embed_index

            # Calculate text statistics
            text_stats = self._calculate_text_stats(df_source, config_list)

            # Build metadata response
            meta: dict[str, Any] = {
                "kb_id": str(uuid.uuid4()),
                "kb_name": self.kb_name,
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
            self.status = f"✅ KB **{self.kb_name}** saved · {len(df_source)} rows, {vector_count} embedded."

            return Data(data=meta)

        except Exception as e:
            if not self.silent_errors:
                raise
            self.log(f"Error in KB ingestion: {e}")
            self.status = f"❌ KB ingestion failed: {e}"
            return Data(data={"error": str(e), "kb_name": self.kb_name})

    def status_message(self) -> Message:
        """Return the human-readable status string."""
        return Message(text=self.status or "KB ingestion completed.")

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None) -> dotdict:
        """Update build configuration based on provider selection."""
        if field_name == "embedding_provider":
            if field_value == "OpenAI":
                build_config["embedding_model"]["options"] = OPENAI_EMBEDDING_MODEL_NAMES
                build_config["embedding_model"]["value"] = OPENAI_EMBEDDING_MODEL_NAMES[0]
                build_config["api_key"]["display_name"] = "OpenAI API Key"
            elif field_value == "HuggingFace":
                build_config["embedding_model"]["options"] = [
                    "sentence-transformers/all-MiniLM-L6-v2",
                    "sentence-transformers/all-mpnet-base-v2",
                ]
                build_config["embedding_model"]["value"] = "sentence-transformers/all-MiniLM-L6-v2"
                build_config["api_key"]["display_name"] = "HuggingFace API Key"
            elif field_value == "Cohere":
                build_config["embedding_model"]["options"] = ["embed-english-v3.0", "embed-multilingual-v3.0"]
                build_config["embedding_model"]["value"] = "embed-english-v3.0"
                build_config["api_key"]["display_name"] = "Cohere API Key"
            elif field_value == "Custom":
                build_config["embedding_model"]["options"] = ["custom-model"]
                build_config["embedding_model"]["value"] = "custom-model"
                build_config["api_key"]["display_name"] = "Custom API Key"

        return build_config
