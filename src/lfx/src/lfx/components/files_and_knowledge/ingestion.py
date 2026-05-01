from __future__ import annotations

import asyncio
import hashlib
import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import pandas as pd
from cryptography.fernet import InvalidToken
from langchain_chroma import Chroma
from langflow.services.auth.utils import decrypt_api_key, encrypt_api_key
from langflow.services.database.models.user.crud import get_user_by_id

from lfx.base.knowledge_bases.backends import BackendType, BaseVectorStoreBackend, create_backend
from lfx.base.knowledge_bases.ingestion_sources.base import (
    IngestionItemResult,
    IngestionItemStatus,
    IngestionRunStatus,
    IngestionSummary,
)
from lfx.base.knowledge_bases.ingestion_sources.flow_component import FlowComponentSource
from lfx.base.knowledge_bases.knowledge_base_utils import get_knowledge_bases
from lfx.base.models.unified_models import get_embedding_model_options, get_embeddings
from lfx.components.files_and_knowledge._kb_paths import (
    get_knowledge_bases_root_path as _get_knowledge_bases_root_path,
)
from lfx.components.processing.converter import convert_to_dataframe
from lfx.custom import Component
from lfx.io import (
    BoolInput,
    DBProviderInput,
    DropdownInput,
    HandleInput,
    IntInput,
    ModelInput,
    Output,
    SecretStrInput,
    StrInput,
    TableInput,
)
from lfx.schema.data import Data
from lfx.schema.table import EditMode
from lfx.services.deps import (
    get_settings_service,
    session_scope,
)
from lfx.utils.validate_cloud import raise_error_if_astra_cloud_disable_component

if TYPE_CHECKING:
    from pathlib import Path

    from lfx.schema.dataframe import DataFrame

# Error message to raise if we're in Astra cloud environment and the component is not supported.
astra_error_msg = "Knowledge ingestion is not supported in Astra cloud environment."

_DEFAULT_OPENSEARCH_CONFIG = {
    "url_variable": "OPENSEARCH_URL",
    "username_variable": "OPENSEARCH_USERNAME",
    "password_variable": "OPENSEARCH_PASSWORD",  # pragma: allowlist secret
    "index_name": "",
    "vector_field": "vector_field",
    "text_field": "text",
}


class KnowledgeIngestionComponent(Component):
    """Create or append to Langflow Knowledge from a DataFrame."""

    # ------ UI metadata ---------------------------------------------------
    display_name = "Knowledge Ingestion"
    description = "Create or update knowledge in Langflow."
    icon = "upload"
    name = "KnowledgeIngestion"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._cached_kb_path: Path | None = None

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
                        "field_order": [
                            "01_new_kb_name",
                            "02_embedding_model",
                            "03_knowledge_backend",
                        ],
                        "template": {
                            "01_new_kb_name": StrInput(
                                name="new_kb_name",
                                display_name="Knowledge Name",
                                info="Name of the new knowledge to create.",
                                required=True,
                            ),
                            "02_embedding_model": ModelInput(
                                name="embedding_model",
                                display_name="Choose Embedding Model",
                                info=(
                                    "Select the embedding model to use for this knowledge base. "
                                    "Langflow uses the configured credentials for that model provider."
                                ),
                                required=True,
                                model_type="embedding",
                            ),
                            "03_knowledge_backend": DBProviderInput(
                                name="knowledge_backend",
                                display_name="DB Provider",
                                info=(
                                    "Select where this knowledge base stores vectors. "
                                    "OpenSearch uses the global DB Providers settings."
                                ),
                                # Leave value empty so the frontend defaults to the
                                # user's configured active DB Provider on first render.
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
            display_name="Knowledge",
            info="Select the knowledge to load data from.",
            required=True,
            options=[],
            refresh_button=True,
            real_time_refresh=True,
            dialog_inputs=asdict(NewKnowledgeBaseInput()),
        ),
        HandleInput(
            name="input_df",
            display_name="Input",
            info=(
                "Table with all original columns (already chunked / processed). "
                "Accepts Message, Data, or DataFrame. If Message or Data is provided, "
                "it is converted to a DataFrame automatically."
            ),
            input_types=["Message", "Data", "JSON", "DataFrame", "Table"],
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
            info="Overrides global provider settings. Leave blank to use your pre-configured API Key.",
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
        StrInput(
            name="metadata_json",
            display_name="Metadata",
            info=(
                "Optional JSON object of user metadata applied to every chunk produced by this "
                'run (e.g. {"tag": "invoice", "year": "2026"}). Same shape as the upload modal '
                "Metadata section so chunks browser filters + KnowledgeBaseComponent.metadata_filter "
                "work uniformly across upload, folder, and flow-driven ingestion. Malformed JSON is "
                "ignored with a warning rather than failing the run."
            ),
            advanced=True,
            required=False,
        ),
    ]

    # ------ Outputs -------------------------------------------------------
    outputs = [Output(display_name="Results", name="dataframe_output", method="build_kb_info")]

    # ------ Internal helpers ---------------------------------------------
    def _get_kb_root(self) -> Path:
        """Return the root directory for knowledge bases."""
        return _get_knowledge_bases_root_path()

    @staticmethod
    def _scalar_notna(value) -> bool:
        """Check if a value is not NA, safely handling arrays and sequences.

        ``pd.notna`` returns an array when given an array-like input, which
        cannot be used directly in a boolean context.  This helper collapses the
        result to a single scalar ``bool``.
        """
        result = pd.notna(value)
        # If result is array-like (numpy array, list, etc.), treat non-empty arrays as "present"
        if hasattr(result, "__iter__") and not isinstance(result, str):
            import numpy as np

            arr = np.asarray(result)
            return arr.size > 0 and arr.all()
        return bool(result)

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

    def _build_embedding_metadata(
        self,
        model_selection: list[dict[str, Any]],
        api_key: str | None = None,
        backend_type: str = BackendType.CHROMA.value,
        backend_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build embedding model metadata from a model selection dict.

        Args:
            model_selection: Model selection list from ModelInput
                (e.g. [{'name': ..., 'provider': ..., 'metadata': ...}])
            api_key: Optional runtime API key override.
            backend_type: DB provider identifier for vector storage.
            backend_config: Backend-specific config persisted with the KB.
        """
        model_dict = model_selection[0] if isinstance(model_selection, list) else model_selection
        embedding_model = model_dict.get("name", "")
        embedding_provider = model_dict.get("provider", "Unknown")

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

        return {
            "embedding_provider": embedding_provider,
            "embedding_model": embedding_model,
            "model_selection": model_dict,  # Store full selection for get_embeddings() reconstruction
            "api_key": encrypted_api_key,
            "api_key_used": bool(api_key),
            "chunk_size": self.chunk_size,
            "backend_type": backend_type,
            "backend_config": backend_config or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def _save_embedding_metadata(
        self,
        kb_path: Path,
        model_selection: list[dict[str, Any]],
        api_key: str | None = None,
        backend_type: str | None = None,
        backend_config: dict[str, Any] | None = None,
    ) -> None:
        """Save embedding model metadata."""
        metadata_path = kb_path / "embedding_metadata.json"
        existing_metadata: dict[str, Any] = {}
        if metadata_path.exists():
            try:
                existing_metadata = json.loads(metadata_path.read_text())
            except (OSError, json.JSONDecodeError):
                existing_metadata = {}

        embedding_metadata = self._build_embedding_metadata(
            model_selection,
            api_key,
            backend_type=backend_type or existing_metadata.get("backend_type") or BackendType.CHROMA.value,
            backend_config=backend_config
            if backend_config is not None
            else existing_metadata.get("backend_config") or {},
        )
        metadata_path.write_text(json.dumps(embedding_metadata, indent=2))

    def _update_metadata_metrics(self, kb_path: Path, chroma: Chroma) -> None:
        """Update embedding_metadata.json with accurate chunk/word/character counts.

        This ensures the Knowledge Base modal displays correct stats after
        component-based ingestion, matching the behavior of API-based ingestion.
        Delegates to KBAnalysisHelper.update_text_metrics to avoid duplicating
        the batched metrics counting logic.
        """
        import chromadb.errors
        from langflow.api.utils.kb_helpers import KBAnalysisHelper, KBStorageHelper

        metadata_path = kb_path / "embedding_metadata.json"
        if not metadata_path.exists():
            return

        try:
            metadata = json.loads(metadata_path.read_text())
            KBAnalysisHelper.update_text_metrics(kb_path, metadata, chroma)
            metadata["size"] = KBStorageHelper.get_directory_size(kb_path)
            metadata_path.write_text(json.dumps(metadata, indent=2))
        except (OSError, ValueError, TypeError, json.JSONDecodeError, chromadb.errors.ChromaError) as e:
            self.log(f"Warning: Could not update metadata metrics: {e}")

    async def _update_backend_metadata_metrics(self, kb_path: Path, backend: BaseVectorStoreBackend) -> None:
        """Update metadata metrics for non-Chroma backends."""
        metadata_path = kb_path / "embedding_metadata.json"
        if not metadata_path.exists():
            return

        try:
            metadata = json.loads(metadata_path.read_text())
            chunks = await backend.count()
            characters = 0
            words = 0
            async for batch in backend.iter_documents():
                for document in batch:
                    characters += len(document.content)
                    words += len(document.content.split())

            metadata["chunks"] = chunks
            metadata["characters"] = characters
            metadata["words"] = words
            metadata["avg_chunk_size"] = characters / chunks if chunks else 0.0
            metadata["size"] = await backend.storage_size_bytes()
            metadata_path.write_text(json.dumps(metadata, indent=2))
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as e:
            self.log(f"Warning: Could not update backend metadata metrics: {e}")

    @staticmethod
    def _normalize_backend_selection(value: Any) -> tuple[str, dict[str, Any]]:
        """Normalize a DBProviderInput value into backend type/config."""
        if not value:
            return BackendType.CHROMA.value, {}

        if isinstance(value, str):
            backend_type = value if value == BackendType.OPENSEARCH.value else BackendType.CHROMA.value
            return (
                backend_type,
                _DEFAULT_OPENSEARCH_CONFIG.copy() if backend_type == BackendType.OPENSEARCH.value else {},
            )

        if not isinstance(value, dict):
            return BackendType.CHROMA.value, {}

        backend_type = str(value.get("backend_type") or value.get("id") or BackendType.CHROMA.value)
        if backend_type != BackendType.OPENSEARCH.value:
            return BackendType.CHROMA.value, {}

        backend_config = value.get("backend_config") or value.get("config") or {}
        if not isinstance(backend_config, dict):
            backend_config = {}
        merged_config = {**_DEFAULT_OPENSEARCH_CONFIG, **backend_config}
        return BackendType.OPENSEARCH.value, merged_config

    @staticmethod
    def _get_backend_from_metadata(kb_path: Path) -> tuple[str, dict[str, Any]]:
        metadata_path = kb_path / "embedding_metadata.json"
        if not metadata_path.exists():
            return BackendType.CHROMA.value, {}
        try:
            metadata = json.loads(metadata_path.read_text())
        except (OSError, json.JSONDecodeError):
            return BackendType.CHROMA.value, {}

        backend_type = str(metadata.get("backend_type") or BackendType.CHROMA.value)
        backend_config = metadata.get("backend_config") or {}
        if not isinstance(backend_config, dict):
            backend_config = {}
        return backend_type, backend_config

    async def _create_knowledge_base_record(
        self,
        *,
        user_id: Any,
        name: str,
        model_selection: list[dict[str, Any]],
        backend_type: str,
        backend_config: dict[str, Any],
    ) -> None:
        """Persist the component-created KB in the DB when Langflow is available."""
        try:
            from langflow.api.utils import knowledge_base_service
        except ImportError:
            return

        try:
            await knowledge_base_service.create_record(
                user_id=user_id,
                name=name,
                model_selection=model_selection,
                column_config=self.column_config if isinstance(self.column_config, list) else [],
                backend_type=backend_type,
                backend_config=backend_config,
            )
        except Exception as exc:  # noqa: BLE001
            self.log(f"Warning: could not persist knowledge base record: {exc}")

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

    async def _create_vector_store(
        self,
        df_source: pd.DataFrame,
        config_list: list[dict[str, Any]],
        embedding_function,
    ) -> BaseVectorStoreBackend:
        """Create vector store using the configured DB provider."""
        # Set up vector store directory
        vector_store_dir = await self._kb_path()
        if not vector_store_dir:
            msg = "Knowledge base path is not set. Please create a new knowledge base first."
            raise ValueError(msg)
        vector_store_dir.mkdir(parents=True, exist_ok=True)

        backend_type, backend_config = self._get_backend_from_metadata(vector_store_dir)
        backend = create_backend(
            backend_type,
            kb_name=self.knowledge_base,
            kb_path=vector_store_dir,
            backend_config=backend_config,
            embedding_function=embedding_function,
            user_id=self.user_id,
        )
        await backend.ensure_ready()

        existing_ids = None
        if backend_type != BackendType.CHROMA.value and not self.allow_duplicates:
            existing_ids = set()
            async for batch in backend.iter_documents():
                for document in batch:
                    doc_id = document.metadata.get("_id")
                    if doc_id:
                        existing_ids.add(doc_id)

        # Convert DataFrame to Data objects (following Local DB pattern)
        data_objects = await self._convert_df_to_data_objects(df_source, config_list, existing_ids=existing_ids)

        # Resolve user-supplied metadata once per run so the chunks share the
        # same source_metadata tag the API path writes. Bad JSON logs + skips
        # — never breaks the flow run.
        user_metadata_tag = self._resolve_user_metadata_tag()

        # Convert Data objects to LangChain Documents
        documents = []
        for data_obj in data_objects:
            doc = data_obj.to_lc_document()
            if user_metadata_tag:
                # Match the chunk-metadata key the chunks endpoint and
                # KnowledgeBaseComponent.metadata_filter both look up.
                doc.metadata["source_metadata"] = user_metadata_tag
            documents.append(doc)

        # Add documents to vector store
        if documents:
            await backend.add_documents(documents)
            self.log(f"Added {len(documents)} documents to vector store '{self.knowledge_base}'")

        return backend

    async def _convert_df_to_data_objects(
        self,
        df_source: pd.DataFrame,
        config_list: list[dict[str, Any]],
        existing_ids: set[str] | None = None,
    ) -> list[Data]:
        """Convert DataFrame to Data objects for vector store."""
        data_objects: list[Data] = []

        if existing_ids is None:
            # Set up vector store directory
            kb_path = await self._kb_path()

            # If we don't allow duplicates, we need to get the existing hashes
            chroma = Chroma(
                persist_directory=str(kb_path),
                collection_name=self.knowledge_base,
            )

            # Get all documents and their metadata
            all_docs = chroma.get()

            # Extract all _id values from metadata
            existing_ids = {metadata.get("_id") for metadata in all_docs["metadatas"] if metadata.get("_id")}

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
            identifier_parts = [str(row[col]) for col in content_cols if col in row and self._scalar_notna(row[col])]

            # Join all parts into a single string
            page_content = " ".join(identifier_parts)

            # Build metadata from NON-vectorized columns only (simple key-value pairs)
            data_dict = {
                "text": page_content,  # Main content for vectorization
            }

            # Add identifier columns if they exist
            if identifier_cols:
                identifier_parts = [
                    str(row[col]) for col in identifier_cols if col in row and self._scalar_notna(row[col])
                ]
                page_content = " ".join(identifier_parts)

            # Add metadata columns as simple key-value pairs
            for col in df_source.columns:
                if col not in content_cols and col in row and self._scalar_notna(row[col]):
                    # Convert to simple types for Chroma metadata
                    value = row[col]
                    data_dict[col] = str(value)  # Convert complex types to string

            # Hash the page_content for unique ID
            page_content_hash = hashlib.sha256(page_content.encode()).hexdigest()
            data_dict["_id"] = page_content_hash

            # If duplicates are disallowed, and hash exists, prevent adding this row
            if not self.allow_duplicates and page_content_hash in existing_ids:
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

    async def _kb_path(self) -> Path | None:
        # Check if we already have the path cached
        cached_path = getattr(self, "_cached_kb_path", None)
        if cached_path is not None:
            return cached_path

        # If not cached, compute it
        async with session_scope() as db:
            if not self.user_id:
                msg = "User ID is required for fetching knowledge base path."
                raise ValueError(msg)
            current_user = await get_user_by_id(db, self.user_id)
            if not current_user:
                msg = f"User with ID {self.user_id} not found."
                raise ValueError(msg)
            kb_user = current_user.username

        kb_root = self._get_kb_root()

        # Cache the result
        self._cached_kb_path = kb_root / kb_user / self.knowledge_base

        return self._cached_kb_path

    def _resolve_user_metadata_tag(self) -> str:
        """Return the JSON-encoded user metadata tag for chunk writes.

        Mirrors the API-path contract: every chunk gets a single
        ``source_metadata`` key whose value is a JSON-string holding the
        run-level user metadata. Empty / missing / malformed input
        returns ``""`` so downstream code can do a falsy check and skip
        the metadata stamp entirely.
        """
        raw = getattr(self, "metadata_json", None)
        if not raw:
            return ""
        text = raw.strip() if isinstance(raw, str) else raw
        if not text:
            return ""
        try:
            decoded = json.loads(text)
        except (TypeError, json.JSONDecodeError) as exc:
            self.log(f"KnowledgeIngestionComponent: metadata_json is not valid JSON ({exc}); skipping metadata stamp.")
            return ""
        if not isinstance(decoded, dict):
            self.log(
                "KnowledgeIngestionComponent: metadata_json must decode to a JSON object; skipping metadata stamp."
            )
            return ""
        # Re-encode after parse so the stored value is canonical (no
        # leading whitespace, sorted keys for stable equality).
        return json.dumps(decoded, sort_keys=True)

    # ---------------------------------------------------------------------
    #                         OUTPUT METHODS
    # ---------------------------------------------------------------------
    async def build_kb_info(self) -> Data:
        """Main ingestion routine → returns a dict with KB metadata."""
        # Check if we're in Astra cloud environment and raise an error if we are.
        raise_error_if_astra_cloud_disable_component(astra_error_msg)

        # Run-tracking handles. Set up before the main try so the finally
        # block can finalize even if an early step (validation, kb_path
        # resolution) raises. Failures inside ``_begin_ingestion_run``
        # are swallowed and leave these as ``None`` — ingestion proceeds
        # without a run-history entry rather than blocking on telemetry.
        run_id: uuid.UUID | None = None
        run_job_id: uuid.UUID | None = None
        run_summary: IngestionSummary | None = None
        run_status: IngestionRunStatus = IngestionRunStatus.SUCCEEDED
        run_error: str | None = None
        kb_record_id: uuid.UUID | None = None
        try:
            input_value = self.input_df[0] if isinstance(self.input_df, list) else self.input_df
            df_source: DataFrame = convert_to_dataframe(input_value, auto_parse=False)

            # Validate column configuration (using Structured Output patterns)
            config_list = self._validate_column_config(df_source)
            column_metadata = self._build_column_metadata(config_list, df_source)

            # Read the embedding info from the knowledge base folder
            kb_path = await self._kb_path()
            if not kb_path:
                msg = "Knowledge base path is not set. Please create a new knowledge base first."
                raise ValueError(msg)
            metadata_path = kb_path / "embedding_metadata.json"
            api_key = None
            model_selection = None

            # Read stored metadata
            if metadata_path.exists():
                settings_service = get_settings_service()
                stored_metadata = json.loads(metadata_path.read_text())

                # Prefer stored model_selection dict (new format)
                model_selection = stored_metadata.get("model_selection")
                if model_selection:
                    model_selection = [model_selection] if isinstance(model_selection, dict) else model_selection
                else:
                    # Backward compat: reconstruct from old string-based metadata
                    embedding_model_name = stored_metadata.get("embedding_model")
                    embedding_provider = stored_metadata.get("embedding_provider", "Unknown")
                    if embedding_model_name:
                        # Look up full model info from available options
                        try:
                            all_options = get_embedding_model_options(user_id=self.user_id)
                            match = next(
                                (o for o in all_options if o.get("name") == embedding_model_name),
                                None,
                            )
                            if match:
                                model_selection = [match]
                            else:
                                self.log(
                                    f"Embedding model '{embedding_model_name}' (provider: {embedding_provider}) "
                                    "from stored metadata is no longer available in the model registry. "
                                    "Please re-create this knowledge base with a supported embedding model."
                                )
                                msg = (
                                    f"Embedding model '{embedding_model_name}' is no longer recognized. "
                                    "The knowledge base was created with an older format and the model "
                                    "is not available in the current registry. "
                                    "Please re-create the knowledge base with a supported embedding model."
                                )
                                raise ValueError(msg)
                        except ValueError:
                            raise
                        except Exception:  # noqa: BLE001
                            self.log(
                                f"Failed to look up embedding model '{embedding_model_name}' in registry. "
                                "Please re-create this knowledge base with a supported embedding model."
                            )
                            msg = (
                                f"Could not look up embedding model '{embedding_model_name}' "
                                f"(provider: {embedding_provider}). "
                                "Please re-create the knowledge base with a supported embedding model."
                            )
                            raise ValueError(msg)  # noqa: B904

                # Decrypt stored API key
                encrypted_key = stored_metadata.get("api_key")
                if encrypted_key:
                    try:
                        api_key = decrypt_api_key(encrypted_key, settings_service)
                    except (InvalidToken, TypeError, ValueError) as e:
                        self.log(f"Could not decrypt API key. Please provide it manually. Error: {e}")

            # Check if a custom API key was provided
            if self.api_key:
                api_key = self.api_key
                if model_selection:
                    self._save_embedding_metadata(
                        kb_path=kb_path,
                        model_selection=model_selection,
                        api_key=api_key,
                    )

            if not model_selection:
                msg = "No embedding model configuration found. Please create the knowledge base first."
                raise ValueError(msg)

            # Build the embedding function via the shared utility
            embedding_function = get_embeddings(
                model=model_selection,
                user_id=self.user_id,
                api_key=api_key,
                chunk_size=self.chunk_size,
            )

            # Begin run tracking once we know we have everything we need
            # to actually start writing. Done after embedding/model
            # validation so a misconfigured KB doesn't pollute the run
            # history with PENDING runs that never start.
            run_id, run_job_id, run_summary, kb_record_id = await self._begin_ingestion_run(kb_path)
            # Mirror Path A: flip the KB row to INGESTING so the UI shows
            # an in-flight state instead of stale "ready".
            if kb_record_id is not None:
                await self._record_kb_status(kb_record_id, "ingesting")

            # Create vector store using the configured DB provider
            backend = await self._create_vector_store(df_source, config_list, embedding_function=embedding_function)

            # Save KB files (using File Component storage patterns)
            self._save_kb_files(kb_path, config_list)

            # Update embedding_metadata.json with accurate text metrics
            # so the KB modal and API show correct chunks/words/characters
            try:
                if not isinstance(backend, BaseVectorStoreBackend):
                    pass
                elif backend.backend_type == BackendType.CHROMA and hasattr(backend, "raw_langchain_store"):
                    self._update_metadata_metrics(kb_path, backend.raw_langchain_store())
                else:
                    await self._update_backend_metadata_metrics(kb_path, backend)
            finally:
                if isinstance(backend, BaseVectorStoreBackend):
                    await backend.teardown()

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

            # Record the DataFrame as one succeeded item against the run
            # so the run-history detail view shows row + chunk counts.
            # No per-row breakdown — the flow component receives a single
            # DataFrame and writes it as one logical batch.
            if run_summary is not None:
                run_summary.record_item(
                    IngestionItemResult(
                        item_id=self.knowledge_base,
                        display_name=f"{self.knowledge_base} ({len(df_source)} rows)",
                        status=IngestionItemStatus.SUCCEEDED,
                        chunks_created=len(df_source),
                    ),
                )

            # Mirror Path A: push the freshly-refreshed text/byte metrics
            # from embedding_metadata.json back onto the KB DB row so the
            # KB list page shows accurate counts. Without this, the UI
            # reads stale row stats even though chunks landed correctly.
            if kb_record_id is not None:
                await self._record_kb_stats(kb_record_id, kb_path)
                await self._record_kb_status(kb_record_id, "ready")

            # Set status message
            self.status = f"✅ KB **{self.knowledge_base}** saved · {len(df_source)} chunks."

            return Data(data=meta)

        except (OSError, ValueError, RuntimeError, KeyError) as e:
            run_status = IngestionRunStatus.FAILED
            run_error = str(e) or e.__class__.__name__
            msg = f"Error during KB ingestion: {e}"
            raise RuntimeError(msg) from e
        except Exception as e:
            run_status = IngestionRunStatus.FAILED
            run_error = str(e) or e.__class__.__name__
            raise
        finally:
            if run_id is not None and run_summary is not None:
                await self._finalize_ingestion_run(
                    run_id=run_id,
                    job_id=run_job_id,
                    summary=run_summary,
                    status=run_status,
                    error_message=run_error,
                )
            # Status sync runs unconditionally (independent of run-tracking
            # success) — a KB stuck in INGESTING with no follow-up update
            # is worse than a missed run-history entry.
            if kb_record_id is not None and run_status is IngestionRunStatus.FAILED:
                await self._record_kb_status(kb_record_id, "failed", failure_reason=run_error)

    async def _begin_ingestion_run(
        self,
        kb_path: Path,
    ) -> tuple[uuid.UUID | None, uuid.UUID | None, IngestionSummary | None, uuid.UUID | None]:
        """Create a parent ``Job`` and seed an ingestion-run row.

        Mirrors the ``perform_ingestion`` setup so flow-component
        ingestions show up in the same run-history UI as file uploads.
        Best-effort: any failure is logged and returns ``(None, None,
        None)`` so the actual ingestion still proceeds — telemetry must
        not block writing data to the vector store.

        Returns ``(run_id, job_id, summary)``. ``run_id`` and ``job_id``
        are equal post the ``ingestion_run`` table cutover, but the
        helpers still take both so the contract matches Path A.
        """
        # Without a user we can't link the run to the requester, and
        # ``Job.user_id IS NULL`` rows don't appear in the per-user
        # runs list. Skip rather than write an orphaned row.
        if not self.user_id:
            self.log("No user_id on component; skipping ingestion-run tracking.")
            return None, None, None, None

        try:
            user_uuid = uuid.UUID(str(self.user_id))
        except (ValueError, TypeError) as exc:
            self.log(f"Could not coerce user_id={self.user_id!r} to UUID; skipping run tracking ({exc}).")
            return None, None, None, None

        try:
            from langflow.api.utils import ingestion_run_service, knowledge_base_service
            from langflow.services.database.models.jobs.model import JobStatus, JobType
            from langflow.services.deps import get_job_service
        except ImportError as exc:
            self.log(f"Run-history wiring unavailable; ingestion will not be recorded ({exc}).")
            return None, None, None, None

        try:
            kb_record = await knowledge_base_service.get_by_user_and_name(
                user_uuid, self.knowledge_base
            )
            kb_record_id = kb_record.id if kb_record is not None else None

            user_metadata = self._parse_user_metadata_dict()

            job_id = uuid.uuid4()
            job_service = get_job_service()
            # ``flow_id`` is required on Job; fall back to the job_id
            # itself when the component is invoked outside a flow run
            # (rare but legal — direct API instantiation, tests).
            raw_flow_id = getattr(self, "flow_id", None)
            flow_id_uuid = uuid.UUID(str(raw_flow_id)) if raw_flow_id else job_id
            await job_service.create_job(
                job_id=job_id,
                flow_id=flow_id_uuid,
                job_type=JobType.INGESTION,
                asset_id=kb_record_id,
                asset_type="knowledge_base",
                user_id=user_uuid,
            )
            await job_service.update_job_status(job_id, JobStatus.IN_PROGRESS)

            source = FlowComponentSource(
                user_id=user_uuid,
                source_config={
                    "knowledge_base": self.knowledge_base,
                    "kb_path": str(kb_path),
                    "flow_id": str(flow_id_uuid),
                },
            )

            run_id = await ingestion_run_service.create_run(
                kb_name=self.knowledge_base,
                source=source,
                job_id=job_id,
                user_id=user_uuid,
                kb_id=kb_record_id,
                user_metadata=user_metadata,
            )
            if run_id is None:
                return None, job_id, None, kb_record_id
            await ingestion_run_service.mark_running(run_id)

            summary = IngestionSummary(
                kb_name=self.knowledge_base,
                source_type=source.source_type.value,
                user_id=user_uuid,
                job_id=job_id,
                source_config=source.describe().get("config") or {},
                user_metadata=user_metadata,
            )
            self.log(
                f"Started ingestion run job_id={job_id} kb_name={self.knowledge_base} "
                f"kb_id={kb_record_id}"
            )
        except Exception as exc:  # noqa: BLE001 — telemetry must never abort ingestion
            self.log(f"Could not begin ingestion-run tracking: {exc}")
            return None, None, None, None
        else:
            return run_id, job_id, summary, kb_record_id

    async def _finalize_ingestion_run(
        self,
        *,
        run_id: uuid.UUID,
        job_id: uuid.UUID | None,
        summary: IngestionSummary,
        status: IngestionRunStatus,
        error_message: str | None,
    ) -> None:
        """Persist the final summary and transition the parent Job.

        Best-effort: errors are logged and never re-raised — the
        ingestion has already succeeded (or already raised) by the time
        we land here, so a missed status update should not change what
        the caller sees.
        """
        try:
            from langflow.api.utils import ingestion_run_service
            from langflow.services.database.models.jobs.model import JobStatus
            from langflow.services.deps import get_job_service
        except ImportError as exc:
            self.log(f"Run-history wiring unavailable; ingestion-run finalize skipped ({exc}).")
            return

        try:
            await ingestion_run_service.finalize_run(
                run_id,
                summary=summary,
                status=status,
                error_message=error_message,
            )
            if job_id is not None:
                terminal_status = (
                    JobStatus.COMPLETED if status is not IngestionRunStatus.FAILED else JobStatus.FAILED
                )
                await get_job_service().update_job_status(
                    job_id, terminal_status, finished_timestamp=True
                )
        except Exception as exc:  # noqa: BLE001 — telemetry must never re-raise
            self.log(f"Could not finalize ingestion-run tracking: {exc}")

    async def _record_kb_status(
        self,
        kb_record_id: uuid.UUID,
        status_value: str,
        *,
        failure_reason: str | None = None,
    ) -> None:
        """Mirror Path A's KB-row status transitions.

        ``status_value`` is the string form ("ingesting" / "ready" /
        "failed") so the helper doesn't need to import
        ``KnowledgeBaseStatus`` at module scope (langflow-only).
        """
        try:
            from langflow.api.utils import knowledge_base_service
            from langflow.services.database.models.knowledge_base.model import KnowledgeBaseStatus
        except ImportError:
            return
        try:
            await knowledge_base_service.update_status(
                kb_record_id,
                status=KnowledgeBaseStatus(status_value),
                failure_reason=failure_reason,
            )
        except Exception as exc:  # noqa: BLE001
            self.log(f"Could not update KB status to {status_value}: {exc}")

    async def _record_kb_stats(self, kb_record_id: uuid.UUID, kb_path: Path) -> None:
        """Push freshly-refreshed metrics from embedding_metadata.json onto the DB row.

        The component's ``_update_*_metadata_metrics`` methods rewrite
        the on-disk JSON; this helper mirrors those values onto the
        ``knowledge_base`` row so the KB list / detail UI doesn't show
        stale chunk / word / character counts after a flow-driven
        ingestion.
        """
        try:
            from langflow.api.utils import knowledge_base_service
        except ImportError:
            self.log("knowledge_base_service unavailable; KB stats will not sync to DB row.")
            return
        metadata_path = kb_path / "embedding_metadata.json"
        if not metadata_path.exists():
            self.log(f"No embedding_metadata.json at {metadata_path}; skipping KB stats sync.")
            return
        try:
            metadata = json.loads(metadata_path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            self.log(f"Could not read KB metadata for stats sync: {exc}")
            return
        chunks = int(metadata.get("chunks", 0) or 0)
        words = int(metadata.get("words", 0) or 0)
        characters = int(metadata.get("characters", 0) or 0)
        try:
            await knowledge_base_service.update_stats(
                kb_record_id,
                chunks=chunks,
                words=words,
                characters=characters,
                size_bytes=int(metadata.get("size", 0) or 0),
                source_types=list(metadata.get("source_types") or []),
                chunk_size=metadata.get("chunk_size"),
                chunk_overlap=metadata.get("chunk_overlap"),
                separator=metadata.get("separator"),
            )
            self.log(
                f"Synced KB stats to DB row {kb_record_id}: "
                f"chunks={chunks} words={words} characters={characters}"
            )
        except Exception as exc:  # noqa: BLE001
            self.log(f"Could not sync KB stats to DB row {kb_record_id}: {exc}")

    def _parse_user_metadata_dict(self) -> dict[str, Any]:
        """Decode ``metadata_json`` to a dict, or ``{}`` on any error.

        Distinct from ``_resolve_user_metadata_tag`` (which returns the
        canonical JSON *string* stamped onto each chunk's
        ``source_metadata`` key). The run-history layer wants a real
        dict — that's what ``ingestion_run_service.create_run`` and
        ``IngestionSummary.user_metadata`` expect.
        """
        raw = getattr(self, "metadata_json", None)
        if not raw:
            return {}
        text = raw.strip() if isinstance(raw, str) else raw
        if not text:
            return {}
        try:
            decoded = json.loads(text)
        except (TypeError, json.JSONDecodeError):
            return {}
        return decoded if isinstance(decoded, dict) else {}

    async def update_build_config(
        self,
        build_config,
        field_value: Any,
        field_name: str | None = None,
    ):
        """Update build configuration based on provider selection."""
        # Check if we're in Astra cloud environment and raise an error if we are.
        raise_error_if_astra_cloud_disable_component(astra_error_msg)

        # Populate the dialog's embedding model options so the ModelInput renders correctly
        try:
            dialog_template = (
                build_config["knowledge_base"]
                .get("dialog_inputs", {})
                .get("fields", {})
                .get("data", {})
                .get("node", {})
                .get("template", {})
            )
            if "02_embedding_model" in dialog_template:
                embedding_options = get_embedding_model_options(user_id=self.user_id)
                dialog_template["02_embedding_model"]["options"] = embedding_options
        except Exception:  # noqa: BLE001
            self.log("Failed to populate embedding model options in dialog")

        # Create a new knowledge base
        if field_name == "knowledge_base":
            async with session_scope() as db:
                if not self.user_id:
                    msg = "User ID is required for fetching knowledge base list."
                    raise ValueError(msg)
                current_user = await get_user_by_id(db, self.user_id)
                if not current_user:
                    msg = f"User with ID {self.user_id} not found."
                    raise ValueError(msg)
                kb_user = current_user.username
            if isinstance(field_value, dict) and "01_new_kb_name" in field_value:
                # Validate the knowledge base name - Make sure it follows these rules:
                if not self.is_valid_collection_name(field_value["01_new_kb_name"]):
                    msg = f"Invalid knowledge base name: {field_value['01_new_kb_name']}"
                    raise ValueError(msg)

                # The model selection comes from ModelInput as a list of dicts
                model_selection = field_value["02_embedding_model"]
                if isinstance(model_selection, dict):
                    model_selection = [model_selection]

                backend_type, backend_config = self._normalize_backend_selection(
                    field_value.get("03_knowledge_backend")
                )

                # Build and validate the embedding model via the shared utility
                embed_model = get_embeddings(
                    model=model_selection,
                    user_id=self.user_id,
                )

                # Try to generate a dummy embedding to validate without blocking the event loop
                try:
                    await asyncio.wait_for(
                        asyncio.to_thread(embed_model.embed_query, "test"),
                        timeout=10,
                    )
                except TimeoutError as e:
                    msg = "Embedding validation timed out. Please verify network connectivity and key."
                    raise ValueError(msg) from e
                except Exception as e:
                    msg = f"Embedding validation failed: {e!s}"
                    raise ValueError(msg) from e

                # Create the new knowledge base directory
                kb_path = _get_knowledge_bases_root_path() / kb_user / field_value["01_new_kb_name"]
                kb_path.mkdir(parents=True, exist_ok=True)

                # Save the embedding metadata
                build_config["knowledge_base"]["value"] = field_value["01_new_kb_name"]
                self._save_embedding_metadata(
                    kb_path=kb_path,
                    model_selection=model_selection,
                    backend_type=backend_type,
                    backend_config=backend_config,
                )
                await self._create_knowledge_base_record(
                    user_id=self.user_id,
                    name=field_value["01_new_kb_name"],
                    model_selection=model_selection,
                    backend_type=backend_type,
                    backend_config=backend_config,
                )

            # Update the knowledge base options dynamically
            build_config["knowledge_base"]["options"] = await get_knowledge_bases(
                _get_knowledge_bases_root_path(),
                user_id=self.user_id,
            )

            # If the selected knowledge base is not available, reset it
            if build_config["knowledge_base"]["value"] not in build_config["knowledge_base"]["options"]:
                build_config["knowledge_base"]["value"] = None

        return build_config
