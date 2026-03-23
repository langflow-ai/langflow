from __future__ import annotations

import asyncio
import hashlib
import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd
from cryptography.fernet import InvalidToken
from langchain_chroma import Chroma
from langflow.services.auth.utils import decrypt_api_key, encrypt_api_key
from langflow.services.database.models.user.crud import get_user_by_id

from lfx.base.knowledge_bases.knowledge_base_utils import get_knowledge_bases
from lfx.base.models.unified_models import get_embedding_model_options, get_embeddings
from lfx.components.processing.converter import convert_to_dataframe
from lfx.custom import Component
from lfx.io import (
    BoolInput,
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
    from lfx.schema.dataframe import DataFrame

_KNOWLEDGE_BASES_ROOT_PATH: Path | None = None

# Error message to raise if we're in Astra cloud environment and the component is not supported.
astra_error_msg = "Knowledge ingestion is not supported in Astra cloud environment."


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
                            "03_api_key",
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
                                info="Select the embedding model to use for this knowledge base.",
                                required=True,
                                model_type="embedding",
                            ),
                            "03_api_key": SecretStrInput(
                                name="api_key",
                                display_name="Embedding Provider API Key",
                                info="Optional API key override used to validate and save this knowledge base.",
                                required=False,
                                advanced=True,
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
    ]

    # ------ Outputs -------------------------------------------------------
    outputs = [Output(display_name="Results", name="dataframe_output", method="build_kb_info")]

    # ------ Internal helpers ---------------------------------------------
    def _get_kb_root(self) -> Path:
        """Return the root directory for knowledge bases."""
        return _get_knowledge_bases_root_path()

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
    ) -> dict[str, Any]:
        """Build embedding model metadata from a model selection dict.

        Args:
            model_selection: Model selection list from ModelInput
                (e.g. [{'name': ..., 'provider': ..., 'metadata': ...}])
            api_key: Optional API key override.
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
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def _save_embedding_metadata(
        self,
        kb_path: Path,
        model_selection: list[dict[str, Any]],
        api_key: str | None = None,
    ) -> None:
        """Save embedding model metadata."""
        embedding_metadata = self._build_embedding_metadata(model_selection, api_key)
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

    async def _create_vector_store(
        self,
        df_source: pd.DataFrame,
        config_list: list[dict[str, Any]],
        embedding_function,
    ) -> None:
        """Create vector store following Local DB component pattern."""
        try:
            # Set up vector store directory
            vector_store_dir = await self._kb_path()
            if not vector_store_dir:
                msg = "Knowledge base path is not set. Please create a new knowledge base first."
                raise ValueError(msg)
            vector_store_dir.mkdir(parents=True, exist_ok=True)

            # Convert DataFrame to Data objects (following Local DB pattern)
            data_objects = await self._convert_df_to_data_objects(df_source, config_list)

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

    async def _convert_df_to_data_objects(
        self, df_source: pd.DataFrame, config_list: list[dict[str, Any]]
    ) -> list[Data]:
        """Convert DataFrame to Data objects for vector store."""
        data_objects: list[Data] = []

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

    # ---------------------------------------------------------------------
    #                         OUTPUT METHODS
    # ---------------------------------------------------------------------
    async def build_kb_info(self) -> Data:
        """Main ingestion routine → returns a dict with KB metadata."""
        # Check if we're in Astra cloud environment and raise an error if we are.
        raise_error_if_astra_cloud_disable_component(astra_error_msg)
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

            # Create vector store following Local DB component pattern
            await self._create_vector_store(df_source, config_list, embedding_function=embedding_function)

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
            msg = f"Error during KB ingestion: {e}"
            raise RuntimeError(msg) from e

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

                api_key = field_value.get("03_api_key") or None

                # Build and validate the embedding model via the shared utility
                embed_model = get_embeddings(
                    model=model_selection,
                    user_id=self.user_id,
                    api_key=api_key,
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
                    api_key=api_key,
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
