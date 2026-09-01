"""Unified Knowledge component — ingest into or retrieve from a knowledge base.

This component merges what used to live in ``ingestion.py`` and
``retrieval.py`` into a single, mode-driven component. A ``TabInput``
("📥 Ingest" / "🔍 Retrieve") drives which inputs and which output are
visible. The merged shape gives users one node per KB instead of two
parallel ones that always shared the same ``knowledge_base`` picker,
embedding-model metadata, and backend registry.

Both legacy classes (``KnowledgeIngestionComponent``,
``KnowledgeBaseComponent``) remain importable as thin subclasses of
``KnowledgeComponent`` — see the sibling ``ingestion.py`` / ``retrieval.py``
modules — so saved flows continue to load unchanged.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import pandas as pd
from langchain_chroma import Chroma

from lfx.base.knowledge_bases.backends import BackendType, BaseVectorStoreBackend, create_backend, is_local_chroma
from lfx.base.knowledge_bases.ingestion_sources.base import (
    IngestionItemResult,
    IngestionItemStatus,
    IngestionRunStatus,
    IngestionSummary,
)
from lfx.base.knowledge_bases.ingestion_sources.flow_component import FlowComponentSource
from lfx.base.knowledge_bases.knowledge_base_utils import get_knowledge_bases
from lfx.base.knowledge_bases.validation import (
    is_valid_collection_name as is_valid_kb_collection_name,
)
from lfx.base.knowledge_bases.validation import (
    validate_collection_name,
)
from lfx.base.models.unified_models import get_embedding_model_options, get_embeddings
from lfx.base.vectorstores.chroma_security import chroma_langchain_collection_kwargs
from lfx.components.processing.converter import convert_to_dataframe
from lfx.custom import Component
from lfx.io import (
    BoolInput,
    DBProviderInput,
    DropdownInput,
    HandleInput,
    IntInput,
    MessageTextInput,
    ModelInput,
    Output,
    SecretStrInput,
    StrInput,
    TabInput,
    TableInput,
)
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.dotdict import dotdict
from lfx.schema.table import EditMode
from lfx.services.deps import (
    session_scope,
)
from lfx.utils.component_utils import set_current_fields, set_field_display
from lfx.utils.validate_cloud import raise_error_if_astra_cloud_disable_component


def _inputs_for_mode(default_mode: str) -> list:
    """Return a fresh copy of the canonical inputs list with show flags set for the given mode.

    Used by the legacy subclasses so a saved flow keyed on
    ``KnowledgeIngestion`` / ``KnowledgeBase`` lands on a node template
    whose default visibility already matches the pinned mode — no
    "wait for the user to click the mode tab" UX gap on load.
    """
    always_visible = set(KnowledgeComponent.default_keys) | set(KnowledgeComponent.mode_config[default_mode])
    inputs_copy = []
    for inp in KnowledgeComponent.inputs:
        clone = inp.model_copy(deep=True) if hasattr(inp, "model_copy") else inp
        if clone.name == "mode":
            clone.value = default_mode
        else:
            clone.show = clone.name in always_visible
        inputs_copy.append(clone)
    return inputs_copy


if TYPE_CHECKING:
    from pathlib import Path

# Mode constants. Plain-text labels (no emoji) for consistency with the rest of
# Langflow's TabInput palette — see ``MemoryComponent`` for the same convention.
MODE_INGEST = "Ingest"
MODE_RETRIEVE = "Retrieve"


def _is_retrieve_mode(value: Any) -> bool:
    """Lenient mode check: treats any label containing 'Retrieve' as retrieve mode.

    Older saved flows may carry the emoji-prefixed labels ("📥 Ingest" /
    "🔍 Retrieve") this component used to ship with; substring matching
    keeps those loading without forcing a flow rewrite.
    """
    return isinstance(value, str) and "Retrieve" in value


# Error message used by both the ingest and retrieve paths when the user is
# running against an Astra cloud environment that disables these flows.
astra_error_msg = "Knowledge ingestion and retrieval are not supported in Astra cloud environment."

_DEFAULT_OPENSEARCH_CONFIG = {
    "url_variable": "OPENSEARCH_URL",
    "username_variable": "OPENSEARCH_USERNAME",
    "password_variable": "OPENSEARCH_PASSWORD",  # pragma: allowlist secret
    "index_name": "",
    "vector_field": "vector_field",
    "text_field": "text",
}

_DEFAULT_CHROMA_CLOUD_CONFIG = {
    "mode": "cloud",
    "tenant_variable": "CHROMA_TENANT",
    "database_variable": "CHROMA_DATABASE",
    "api_key_variable": "CHROMA_API_KEY",  # pragma: allowlist secret
}


class KnowledgeComponent(Component):
    """One component for both writing into and reading from a Langflow knowledge base.

    A ``TabInput`` switches between ingestion and retrieval. The
    ``update_build_config`` / ``update_outputs`` hooks hide the inputs
    and the output that don't apply to the current mode so the canvas
    node stays focused.
    """

    display_name = "Knowledge"
    description = "Ingest into or retrieve from a Langflow knowledge base."
    icon = "database"
    name = "Knowledge"

    # ------ Mode → visible-fields wiring ---------------------------------
    # ``default_keys`` are inputs always visible regardless of mode.
    # ``mode_config`` lists the inputs unique to each mode; everything outside
    # this set is hidden when its mode is not selected.
    default_keys: list[str] = ["mode", "knowledge_base"]
    mode_config: dict[str, list[str]] = {
        MODE_INGEST: [
            "input_df",
            "column_config",
            "chunk_size",
            "api_key",
            "allow_duplicates",
            "metadata_json",
        ],
        MODE_RETRIEVE: [
            "search_query",
            "top_k",
            "include_metadata",
            "include_embeddings",
            "metadata_filter",
        ],
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._cached_kb_path: Path | None = None

    @staticmethod
    def _embedding_provider_from_selection(selection: Any) -> str | None:
        """Read a provider name from a raw or persisted model selection."""
        if isinstance(selection, list):
            selection = selection[0] if selection else None
        if not isinstance(selection, Mapping):
            return None
        provider = selection.get("provider")
        if not isinstance(provider, str) or not provider.strip():
            return None
        return provider.strip()

    async def _additional_model_provider_policy_ids(self, purpose, parameters=None) -> tuple[str, ...]:
        """Resolve the embedding provider before dialog hooks or runtime secrets.

        New-KB configuration carries its ModelInput inside a dropdown dialog,
        while existing KBs persist the provider in the KB row. Neither is a
        top-level ModelInput, so both must be resolved explicitly before the
        generic component pipeline hydrates ``api_key``.
        """
        from lfx.base.models.provider_registry import resolve_provider_id
        from lfx.services.model_provider_policy import ModelProviderPolicyError

        effective_parameters = parameters if isinstance(parameters, Mapping) else getattr(self, "_parameters", None)
        if not isinstance(effective_parameters, Mapping):
            effective_parameters = {}
        knowledge_value = effective_parameters.get("knowledge_base", getattr(self, "knowledge_base", None))

        if isinstance(knowledge_value, Mapping):
            if "02_embedding_model" not in knowledge_value:
                return ()
            provider = self._embedding_provider_from_selection(knowledge_value.get("02_embedding_model"))
        elif isinstance(knowledge_value, str) and knowledge_value.strip():
            metadata = await self._get_kb_metadata(knowledge_value.strip())
            provider = self._embedding_provider_from_selection(metadata.get("model_selection"))
            if provider is None:
                legacy_provider = metadata.get("embedding_provider")
                provider = legacy_provider.strip() if isinstance(legacy_provider, str) else None
                if provider == "Unknown":
                    provider = None
        else:
            return ()

        if provider is None:
            unknown_provider = "unknown"
            raise ModelProviderPolicyError(unknown_provider, purpose)
        return (resolve_provider_id(provider),)

    @dataclass
    class NewKnowledgeBaseInput:
        functionality: str = "create"
        fields: dict[str, dict] = field(
            default_factory=lambda: {
                "data": {
                    "node": {
                        "name": "create_knowledge_base",
                        "description": "Create new knowledge in Langflow.",
                        "display_name": "Create new Knowledge Base",
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
                                required=True,
                            ),
                        },
                    },
                }
            }
        )

    # ------ Inputs --------------------------------------------------------
    # ``knowledge_base`` is kept at position 0 so legacy tests that check
    # ``component.inputs[0].dialog_inputs`` continue to work.
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
        TabInput(
            name="mode",
            display_name="Mode",
            options=[MODE_INGEST, MODE_RETRIEVE],
            value=MODE_INGEST,
            info="Switch between writing new data into the knowledge base and querying it.",
            real_time_refresh=True,
            tool_mode=True,
        ),
        # --- Ingest-only inputs (default-shown; hidden when mode == Retrieve) -
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
            dynamic=True,
            show=True,
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
            dynamic=True,
            show=True,
        ),
        IntInput(
            name="chunk_size",
            display_name="Chunk Size",
            info="Batch size for processing embeddings",
            advanced=True,
            value=1000,
            dynamic=True,
            show=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="Embedding Provider API Key",
            info="Overrides global provider settings. Leave blank to use your pre-configured API Key.",
            advanced=True,
            required=False,
            dynamic=True,
            show=True,
        ),
        BoolInput(
            name="allow_duplicates",
            display_name="Allow Duplicates",
            info="Allow duplicate rows in the knowledge base",
            advanced=True,
            value=False,
            dynamic=True,
            show=True,
        ),
        StrInput(
            name="metadata_json",
            display_name="Metadata",
            info=(
                "Optional JSON object of user metadata applied to every chunk produced by this "
                'run (e.g. {"tag": "invoice", "year": "2026"}). Same shape as the upload modal '
                "Metadata section so chunks browser filters + Knowledge retrieval metadata_filter "
                "work uniformly across upload, folder, and flow-driven ingestion. Malformed JSON is "
                "ignored with a warning rather than failing the run."
            ),
            advanced=True,
            required=False,
            dynamic=True,
            show=True,
        ),
        # --- Retrieve-only inputs (default-hidden; shown when mode == Retrieve) -
        MessageTextInput(
            name="search_query",
            display_name="Search Query",
            info="Optional search query to filter knowledge base data.",
            tool_mode=True,
            dynamic=True,
            show=False,
        ),
        IntInput(
            name="top_k",
            display_name="Top K Results",
            info="Number of top results to return from the knowledge base.",
            value=5,
            advanced=True,
            required=False,
            dynamic=True,
            show=False,
        ),
        BoolInput(
            name="include_metadata",
            display_name="Include Metadata",
            info="Whether to include all metadata in the output. If false, only content is returned.",
            value=True,
            advanced=False,
            dynamic=True,
            show=False,
        ),
        BoolInput(
            name="include_embeddings",
            display_name="Include Embeddings",
            info="Whether to include embeddings in the output. Only applicable if 'Include Metadata' is enabled.",
            value=False,
            advanced=True,
            dynamic=True,
            show=False,
        ),
        MessageTextInput(
            name="metadata_filter",
            display_name="Metadata Filter",
            info=(
                "Optional JSON object of user-metadata key/value pairs. Only chunks "
                'whose source_metadata matches every key are returned (e.g. {"tag": "invoice"} '
                'or {"tag": ["invoice", "audit"]} for OR-of-values). Backends without '
                "native filtering apply the match client-side after retrieval."
            ),
            advanced=True,
            dynamic=True,
            show=False,
        ),
    ]

    # ------ Outputs -------------------------------------------------------
    # Both outputs are declared at the class level so the runtime can
    # dispatch to either method depending on which one the saved flow has
    # wired up. ``update_outputs`` filters the canvas-visible output per
    # selected mode; see ``TypeConverterComponent`` and ``MemoryComponent``
    # for the same pattern.
    #
    # Output names match the legacy ``KnowledgeIngestionComponent``
    # (``dataframe_output``) and ``KnowledgeBaseComponent``
    # (``retrieve_data``) so saved flow edges keyed on those names resolve
    # cleanly against the merged component.
    outputs = [
        Output(
            display_name="Results",
            name="dataframe_output",
            method="build_kb_info",
            types=["JSON"],
            selected="JSON",
        ),
        Output(
            display_name="Results",
            name="retrieve_data",
            method="retrieve_data",
            info="Returns the data from the selected knowledge base.",
            types=["Table"],
            selected="Table",
        ),
    ]

    # ------ Mode-driven UI updates ---------------------------------------
    async def update_frontend_node(self, new_frontend_node: dict, current_frontend_node: dict):
        """Sync the visible output with the current ``mode`` value on canvas load.

        Saved flows hit this path: ``update_outputs`` is normally only triggered
        by ``real_time_refresh`` field edits, so without this re-sync the
        canvas could land with both outputs visible.
        """
        await super().update_frontend_node(new_frontend_node, current_frontend_node)
        mode_value = new_frontend_node.get("template", {}).get("mode", {}).get("value", MODE_INGEST)
        self.update_outputs(new_frontend_node, "mode", mode_value)
        return new_frontend_node

    def update_outputs(self, frontend_node: dict, field_name: str, field_value: Any) -> dict:
        """Filter visible outputs to match the selected mode.

        Triggered by the ``mode`` ``TabInput`` ``real_time_refresh`` flag.
        The class-level ``outputs`` list always carries both entries so the
        runtime can resolve either ``build_kb_info`` or ``retrieve_data``
        regardless of canvas visibility — we just hide the unused one here.
        """
        if field_name != "mode":
            return frontend_node
        if _is_retrieve_mode(field_value):
            frontend_node["outputs"] = [
                Output(
                    display_name="Results",
                    name="retrieve_data",
                    method="retrieve_data",
                    info="Returns the data from the selected knowledge base.",
                    types=["Table"],
                    selected="Table",
                )
            ]
        else:
            frontend_node["outputs"] = [
                Output(
                    display_name="Results",
                    name="dataframe_output",
                    method="build_kb_info",
                    types=["JSON"],
                    selected="JSON",
                )
            ]
        return frontend_node

    async def update_build_config(
        self,
        build_config,
        field_value: Any,
        field_name: str | None = None,
    ):
        """Refresh KB options, drive the create-KB dialog, and hide off-mode fields."""
        # Astra-cloud gate covers both ingest and retrieve paths.
        raise_error_if_astra_cloud_disable_component(astra_error_msg)

        # Always populate the create-KB dialog's embedding-model options so the
        # ModelInput renders correctly regardless of which input triggered the
        # refresh.
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

        # KB-picker refresh + create-new-KB flow (lifted from the legacy ingestion
        # component verbatim; relied on by both the canvas refresh button and the
        # dialog-submit path).
        if field_name == "knowledge_base":
            # Lazy import keeps lfx importable without langflow installed.
            from langflow.services.database.models.user.crud import get_user_by_id

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
                model_selection = field_value["02_embedding_model"]
                if isinstance(model_selection, dict):
                    model_selection = [model_selection]

                backend_type, backend_config = self._normalize_backend_selection(
                    field_value.get("03_knowledge_backend")
                )
                new_kb_name = field_value["01_new_kb_name"]
                if backend_type == BackendType.CHROMA.value:
                    validate_collection_name(
                        new_kb_name,
                        resource="Knowledge base",
                        local=is_local_chroma(backend_type, backend_config),
                    )

                embed_model = get_embeddings(
                    model=model_selection,
                    user_id=self.user_id,
                )

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

                # Only local Chroma gets a directory; every remote backend
                # returns None here and creates its collection on first write.
                from langflow.api.utils.kb_helpers import resolve_local_store_path

                resolve_local_store_path(
                    new_kb_name,
                    kb_user,
                    backend_type=backend_type,
                    backend_config=backend_config,
                    create=True,
                )

                build_config["knowledge_base"]["value"] = new_kb_name
                await self._create_knowledge_base_record(
                    user_id=self.user_id,
                    name=field_value["01_new_kb_name"],
                    model_selection=model_selection,
                    backend_type=backend_type,
                    backend_config=backend_config,
                )

            build_config["knowledge_base"]["options"] = await get_knowledge_bases(user_id=self.user_id)
            if build_config["knowledge_base"]["value"] not in build_config["knowledge_base"]["options"]:
                build_config["knowledge_base"]["value"] = None

        # Honor the current mode regardless of which field triggered the refresh.
        # Falls back to MODE_INGEST when ``mode`` is missing (legacy nodes).
        current_mode = build_config.get("mode", {}).get("value") if isinstance(build_config, dict) else None
        if field_name == "mode":
            current_mode = field_value
        # Map legacy/emoji-prefixed labels onto the current canonical values so
        # flows saved before the label change still toggle visibility correctly.
        if _is_retrieve_mode(current_mode):
            current_mode = MODE_RETRIEVE
        elif current_mode not in self.mode_config:
            current_mode = MODE_INGEST
        return set_current_fields(
            build_config=build_config if isinstance(build_config, dotdict) else dotdict(build_config),
            action_fields=self.mode_config,
            selected_action=current_mode,
            default_fields=self.default_keys,
            func=set_field_display,
        )

    # =====================================================================
    #                       INGESTION CODE PATH
    # =====================================================================
    @staticmethod
    def _scalar_notna(value) -> bool:
        """Check if a value is not NA, safely handling arrays and sequences.

        ``pd.notna`` returns an array when given an array-like input, which
        cannot be used directly in a boolean context.  This helper collapses
        the result to a single scalar ``bool``.
        """
        result = pd.notna(value)
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

        config_list = self.column_config if isinstance(self.column_config, list) else []

        df_columns = set(df_source.columns)
        for config in config_list:
            col_name = config.get("column_name")
            if col_name not in df_columns:
                msg = f"Column '{col_name}' not found in DataFrame. Available columns: {sorted(df_columns)}"
                raise ValueError(msg)

        return config_list

    @staticmethod
    def _extract_source_types_from_df(df_source: pd.DataFrame) -> set[str]:
        """Pull file extensions out of common path/name columns on the source DataFrame.

        The direct-upload ingestion path stores extensions in
        the KB row's ``source_types`` so the KB list can render the
        correct file-type icon. When ingestion happens via a connected
        ``input_df`` (e.g. File → Knowledge) the same field stayed empty and
        the icon defaulted to a blank tile. We look at the well-known columns
        the File / S3 / cloud-storage components produce and collect any
        plausible extension so the icon is consistent across both flows.
        """
        candidate_columns = ("file_path", "file_name", "filename", "source", "path", "mimetype")
        extensions: set[str] = set()
        for col in candidate_columns:
            if col not in df_source.columns:
                continue
            for value in df_source[col].dropna():
                ext = KnowledgeComponent._extension_from_value(value)
                # Drop anything that doesn't look like an extension (URL
                # query strings, version segments, etc.) — the icon palette
                # keys off short alphanumeric tokens like "pdf"/"docx".
                if ext:
                    extensions.add(ext)
        return extensions

    @staticmethod
    def _extension_from_value(value: Any) -> str | None:
        """Return a normalized file-extension token from a path / filename / MIME string.

        Accepts values like ``"report.PDF"``, ``"/docs/notes.txt"``, or
        ``"application/pdf"`` and returns ``"pdf"`` / ``"txt"``. Returns
        ``None`` if no plausible extension can be derived.
        """
        extension_length_limit = 10
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        # MIME types like ``application/pdf`` carry the canonical extension
        # in the subtype slot — preserve them so File / S3 messages keyed
        # only on ``mimetype`` still resolve to an icon.
        if "/" in text and "." not in text.rsplit("/", 1)[-1]:
            subtype = text.rsplit("/", 1)[-1].strip().lower()
            return subtype if subtype and len(subtype) <= extension_length_limit and subtype.isalnum() else None
        if "." not in text:
            return None
        ext = text.rsplit(".", 1)[-1].strip().lower()
        if ext and len(ext) <= extension_length_limit and ext.isalnum():
            return ext
        return None

    @classmethod
    def _extract_source_types_from_mapping(cls, mapping: Any) -> set[str]:
        """Pull extensions from a Message/Data-style ``data`` dict or a plain dict."""
        if not isinstance(mapping, dict):
            return set()
        candidate_keys = ("file_path", "file_name", "filename", "source", "path", "mimetype")
        extensions: set[str] = set()
        for key in candidate_keys:
            ext = cls._extension_from_value(mapping.get(key))
            if ext:
                extensions.add(ext)
        return extensions

    @classmethod
    def _extract_source_types_from_input(cls, input_value: Any) -> set[str]:
        """Pull file extensions out of the raw component input.

        ``convert_to_dataframe`` strips Message/Data fields down to ``text``
        when projecting onto a DataFrame, so file metadata attached to a
        File-component "Raw Content" output never reaches
        ``_extract_source_types_from_df``. Looking at the raw input first
        keeps the KB icon consistent with direct upload.
        """
        if input_value is None:
            return set()
        if isinstance(input_value, list):
            extensions: set[str] = set()
            for item in input_value:
                extensions |= cls._extract_source_types_from_input(item)
            return extensions
        if isinstance(input_value, pd.DataFrame):
            return cls._extract_source_types_from_df(input_value)
        # Message / Data / JSON all expose a ``data`` dict via the lfx schema.
        mapping = getattr(input_value, "data", None)
        if mapping is None and isinstance(input_value, dict):
            mapping = input_value
        return cls._extract_source_types_from_mapping(mapping)

    async def _refresh_kb_stats(
        self,
        *,
        kb_record_id: Any,
        backend: BaseVectorStoreBackend,
        extensions: set[str],
    ) -> None:
        """Recount the KB from its vector store and write the totals onto the row.

        Backend-agnostic: counts come from ``count`` / ``iter_documents`` /
        ``storage_size_bytes``, so a Chroma, OpenSearch, or pgVector KB all report
        real numbers. ``extensions`` are merged into ``source_types`` so the KB
        list renders the right file-type icon regardless of which ingestion route
        produced the chunks.

        Best-effort: the chunks are already written and committed by the time this
        runs, so a stats refresh failure must not fail the ingestion.
        """
        if kb_record_id is None:
            return
        try:
            from langflow.api.utils import knowledge_base_service
        except ImportError:
            return

        try:
            chunks = await backend.count()
            characters = 0
            words = 0
            async for batch in backend.iter_documents():
                for document in batch:
                    characters += len(document.content)
                    words += len(document.content.split())

            record = await knowledge_base_service.get_by_id(kb_record_id)
            existing = set(record.source_types or []) if record is not None else set()

            await knowledge_base_service.update_stats(
                kb_record_id,
                chunks=chunks,
                words=words,
                characters=characters,
                size_bytes=await backend.storage_size_bytes(),
                source_types=sorted(existing | extensions),
            )
        except Exception as e:  # noqa: BLE001 — stats are cosmetic; chunks are already written
            self.log(f"Warning: Could not refresh knowledge base stats: {e}")

    @staticmethod
    def _default_backend_selection() -> tuple[str, dict[str, Any]]:
        """Deployment default for a new KB with no explicit backend chosen.

        pgVector is environment-driven: when ``PGVECTOR_CONNECTION_STRING`` is set
        the deployment snap-configures to Postgres, so an unspecified selection
        (headless flows, multi-replica) becomes ``postgres``. Otherwise Chroma.
        """
        from lfx.base.knowledge_bases.backends.postgres import postgres_env_configured

        if postgres_env_configured():
            return BackendType.POSTGRES.value, {}
        return BackendType.CHROMA.value, {}

    @classmethod
    def _normalize_backend_selection(cls, value: Any) -> tuple[str, dict[str, Any]]:
        """Normalize a DBProviderInput value into backend type/config."""
        if not value:
            return cls._default_backend_selection()

        if isinstance(value, str):
            if value == BackendType.OPENSEARCH.value:
                return BackendType.OPENSEARCH.value, _DEFAULT_OPENSEARCH_CONFIG.copy()
            if value == BackendType.POSTGRES.value:
                return BackendType.POSTGRES.value, {}
            return BackendType.CHROMA.value, {}

        if not isinstance(value, dict):
            return BackendType.CHROMA.value, {}

        backend_type = str(value.get("backend_type") or value.get("id") or BackendType.CHROMA.value)

        if backend_type == BackendType.OPENSEARCH.value:
            backend_config = value.get("backend_config") or value.get("config") or {}
            if not isinstance(backend_config, dict):
                backend_config = {}
            return BackendType.OPENSEARCH.value, {**_DEFAULT_OPENSEARCH_CONFIG, **backend_config}

        if backend_type == BackendType.POSTGRES.value:
            return BackendType.POSTGRES.value, {}

        if backend_type == "chroma_cloud":
            backend_config = value.get("backend_config") or value.get("config") or {}
            if not isinstance(backend_config, dict):
                backend_config = {}
            return BackendType.CHROMA.value, {**_DEFAULT_CHROMA_CLOUD_CONFIG, **backend_config}

        return BackendType.CHROMA.value, {}

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

            metadata["columns"].append(
                {
                    "name": col_name,
                    "vectorize": vectorize,
                    "identifier": identifier,
                }
            )

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
        backend_type, backend_config = await self._resolve_backend_config()
        # ``None`` for every remote backend — nothing to create on this box.
        vector_store_dir = self._resolve_store_path(await self._kb_username(), backend_type, backend_config)
        if vector_store_dir is not None:
            vector_store_dir.mkdir(parents=True, exist_ok=True)

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

        data_objects = await self._convert_df_to_data_objects(df_source, config_list, existing_ids=existing_ids)

        user_metadata_tag = self._resolve_user_metadata_tag()

        documents = []
        for data_obj in data_objects:
            doc = data_obj.to_lc_document()
            if user_metadata_tag:
                doc.metadata["source_metadata"] = user_metadata_tag
            documents.append(doc)

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
            # Local-Chroma-only branch: every other backend collects its existing
            # ids through ``iter_documents`` in ``_create_vector_store`` and
            # passes them in, so ``kb_path`` is guaranteed non-None here.
            kb_path = await self._kb_path()
            if kb_path is None:
                existing_ids = set()
            else:
                chroma = Chroma(
                    persist_directory=str(kb_path),
                    collection_name=self.knowledge_base,
                    **chroma_langchain_collection_kwargs(),
                )

                all_docs = chroma.get()

                existing_ids = {metadata.get("_id") for metadata in all_docs["metadatas"] if metadata.get("_id")}

        content_cols = []
        identifier_cols = []

        for config in config_list:
            col_name = config.get("column_name")
            vectorize = config.get("vectorize") == "True" or config.get("vectorize") is True
            identifier = config.get("identifier") == "True" or config.get("identifier") is True

            if vectorize:
                content_cols.append(col_name)
            if identifier:
                identifier_cols.append(col_name)

        for _, row in df_source.iterrows():
            identifier_parts = [str(row[col]) for col in content_cols if col in row and self._scalar_notna(row[col])]

            page_content = " ".join(identifier_parts)

            data_dict = {
                "text": page_content,
            }

            if identifier_cols:
                identifier_parts = [
                    str(row[col]) for col in identifier_cols if col in row and self._scalar_notna(row[col])
                ]
                page_content = " ".join(identifier_parts)

            for col in df_source.columns:
                if col not in content_cols and col in row and self._scalar_notna(row[col]):
                    value = row[col]
                    data_dict[col] = str(value)

            page_content_hash = hashlib.sha256(page_content.encode()).hexdigest()
            data_dict["_id"] = page_content_hash

            if not self.allow_duplicates and page_content_hash in existing_ids:
                self.log(f"Skipping duplicate row with hash {page_content_hash}")
                continue

            data_obj = Data(data=data_dict)
            data_objects.append(data_obj)

        return data_objects

    def is_valid_collection_name(self, name: str) -> bool:
        """Return whether ``name`` satisfies the shared collection-name contract."""
        return is_valid_kb_collection_name(name)

    def _resolve_store_path(
        self,
        kb_user: str,
        backend_type: str,
        backend_config: dict[str, Any] | None,
    ) -> Path | None:
        """Return this KB's on-disk directory, or ``None`` when it needs no disk.

        Only local Chroma stores anything on this box; every other backend
        resolves to ``None`` and never touches the filesystem.
        """
        # Lazy import keeps lfx importable without langflow's DB services.
        from langflow.api.utils.kb_helpers import resolve_local_store_path

        return resolve_local_store_path(
            self.knowledge_base,
            kb_user,
            backend_type=backend_type,
            backend_config=backend_config,
        )

    async def _kb_username(self) -> str:
        """Resolve the owning user's username (used to root a local-Chroma path)."""
        cached = getattr(self, "_cached_kb_username", None)
        if cached is not None:
            return cached

        # Lazy import to keep ``lfx`` importable standalone — langflow's
        # user/DB models are not always available at module load time.
        from langflow.services.database.models.user.crud import get_user_by_id

        async with session_scope() as db:
            if not self.user_id:
                msg = "User ID is required for fetching knowledge base path."
                raise ValueError(msg)
            current_user = await get_user_by_id(db, self.user_id)
            if not current_user:
                msg = f"User with ID {self.user_id} not found."
                raise ValueError(msg)
            self._cached_kb_username = current_user.username

        return self._cached_kb_username

    async def _kb_path(self) -> Path | None:
        """Resolve the KB's local directory from its configured backend."""
        cached_path = getattr(self, "_cached_kb_path", None)
        if cached_path is not None:
            return cached_path

        backend_type, backend_config = await self._resolve_backend_config()
        kb_user = await self._kb_username()
        self._cached_kb_path = self._resolve_store_path(kb_user, backend_type, backend_config)
        return self._cached_kb_path

    def _resolve_user_metadata_tag(self) -> str:
        """Return the JSON-encoded user metadata tag for chunk writes."""
        raw = getattr(self, "metadata_json", None)
        if not raw:
            return ""
        text = raw.strip() if isinstance(raw, str) else raw
        if not text:
            return ""
        try:
            decoded = json.loads(text)
        except (TypeError, json.JSONDecodeError) as exc:
            self.log(f"KnowledgeComponent: metadata_json is not valid JSON ({exc}); skipping metadata stamp.")
            return ""
        if not isinstance(decoded, dict):
            self.log("KnowledgeComponent: metadata_json must decode to a JSON object; skipping metadata stamp.")
            return ""
        return json.dumps(decoded, sort_keys=True)

    async def build_kb_info(self) -> Data:
        """Main ingestion routine → returns a dict with KB metadata.

        The annotation is intentionally narrowed to ``Data`` even though the
        cross-mode fallback below may return a ``DataFrame`` from
        ``retrieve_data``. The frontend builds React-Flow handle IDs from
        this output's type list; widening it to ``Data | DataFrame`` makes
        the API advertise ``["JSON", "Table"]`` for the ingest output and
        breaks every saved-edge sourceHandle that was generated against
        a single-type handle (BUG-02). Python doesn't enforce return
        annotations at runtime, so the rare fallback path keeps working.
        """
        if _is_retrieve_mode(getattr(self, "mode", MODE_INGEST)):
            return await self.retrieve_data()
        raise_error_if_astra_cloud_disable_component(astra_error_msg)

        run_id: uuid.UUID | None = None
        run_job_id: uuid.UUID | None = None
        run_summary: IngestionSummary | None = None
        run_status: IngestionRunStatus = IngestionRunStatus.SUCCEEDED
        run_error: str | None = None
        kb_record_id: uuid.UUID | None = None
        try:
            input_value = self.input_df[0] if isinstance(self.input_df, list) else self.input_df
            df_source: DataFrame = convert_to_dataframe(input_value, auto_parse=False)

            config_list = self._validate_column_config(df_source)
            column_metadata = self._build_column_metadata(config_list, df_source)

            # Embedding config comes from the ``knowledge_base`` row — the sole
            # authority. No sidecar is read, so ingestion resolves the same model
            # on any replica.
            stored_metadata = await self._get_kb_metadata()
            model_selection = stored_metadata.get("model_selection")
            if model_selection:
                model_selection = [model_selection] if isinstance(model_selection, dict) else list(model_selection)
            else:
                embedding_model_name = stored_metadata.get("embedding_model")
                embedding_provider = stored_metadata.get("embedding_provider", "Unknown")
                if embedding_model_name:
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
                                "from the knowledge base record is no longer available in the model registry. "
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

            if not model_selection:
                msg = "No embedding model configuration found. Please create the knowledge base first."
                raise ValueError(msg)

            # ``api_key=None`` falls through to the user's variables table and
            # then the environment inside ``get_embeddings`` — the same
            # resolution the server-side ingestion path uses. The component input
            # only overrides it.
            embedding_function = get_embeddings(
                model=model_selection,
                user_id=self.user_id,
                api_key=self.api_key if getattr(self, "api_key", None) else None,
                chunk_size=self.chunk_size,
            )

            kb_path = await self._kb_path()

            run_id, run_job_id, run_summary, kb_record_id = await self._begin_ingestion_run(kb_path)
            if kb_record_id is not None:
                await self._record_kb_status(kb_record_id, "ingesting")

            backend = await self._create_vector_store(df_source, config_list, embedding_function=embedding_function)

            try:
                # Stamp the KB with the file extensions we just ingested so
                # the Knowledge Bases list renders the correct icon for
                # flow-driven ingestion (input_df), matching direct upload.
                # We look at the raw input first because ``convert_to_dataframe``
                # drops Message/Data metadata fields (file_path, mimetype, …)
                # when projecting onto the DataFrame.
                source_types = self._extract_source_types_from_input(input_value)
                source_types |= self._extract_source_types_from_df(df_source)
                if isinstance(backend, BaseVectorStoreBackend):
                    await self._refresh_kb_stats(
                        kb_record_id=kb_record_id,
                        backend=backend,
                        extensions=source_types,
                    )
            finally:
                if isinstance(backend, BaseVectorStoreBackend):
                    await backend.teardown()

            meta: dict[str, Any] = {
                "kb_id": str(uuid.uuid4()),
                "kb_name": self.knowledge_base,
                "rows": len(df_source),
                "column_metadata": column_metadata,
                "path": str(kb_path),
                "config_columns": len(config_list),
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            }

            if run_summary is not None:
                run_summary.record_item(
                    IngestionItemResult(
                        item_id=self.knowledge_base,
                        display_name=f"{self.knowledge_base} ({len(df_source)} rows)",
                        status=IngestionItemStatus.SUCCEEDED,
                        chunks_created=len(df_source),
                    ),
                )

            if kb_record_id is not None:
                # Stats were already refreshed straight from the backend above.
                await self._record_kb_status(kb_record_id, "ready")

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
            if kb_record_id is not None and run_status is IngestionRunStatus.FAILED:
                await self._record_kb_status(kb_record_id, "failed", failure_reason=run_error)

    async def _begin_ingestion_run(
        self,
        kb_path: Path,
    ) -> tuple[uuid.UUID | None, uuid.UUID | None, IngestionSummary | None, uuid.UUID | None]:
        """Create a parent ``Job`` and seed an ingestion-run row."""
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
            kb_record = await knowledge_base_service.get_by_user_and_name(user_uuid, self.knowledge_base)
            kb_record_id = kb_record.id if kb_record is not None else None

            user_metadata = self._parse_user_metadata_dict()

            job_id = uuid.uuid4()
            job_service = get_job_service()
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
            self.log(f"Started ingestion run job_id={job_id} kb_name={self.knowledge_base} kb_id={kb_record_id}")
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
        """Persist the final summary and transition the parent Job."""
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
                terminal_status = JobStatus.COMPLETED if status is not IngestionRunStatus.FAILED else JobStatus.FAILED
                await get_job_service().update_job_status(job_id, terminal_status, finished_timestamp=True)
        except Exception as exc:  # noqa: BLE001 — telemetry must never re-raise
            self.log(f"Could not finalize ingestion-run tracking: {exc}")

    async def _record_kb_status(
        self,
        kb_record_id: uuid.UUID,
        status_value: str,
        *,
        failure_reason: str | None = None,
    ) -> None:
        """Mirror Path A's KB-row status transitions."""
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

    def _parse_user_metadata_dict(self) -> dict[str, Any]:
        """Decode ``metadata_json`` to a dict, or ``{}`` on any error."""
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

    # =====================================================================
    #                       RETRIEVAL CODE PATH
    # =====================================================================
    @property
    def _user_uuid(self) -> uuid.UUID | None:
        """Return self.user_id as a UUID, converting from str if necessary."""
        if not self.user_id:
            return None
        return self.user_id if isinstance(self.user_id, uuid.UUID) else uuid.UUID(self.user_id)

    async def _get_kb_metadata(self, knowledge_base: str | None = None) -> dict:
        """Load this knowledge base's embedding config from its database row.

        The row is the sole authority. There is no on-disk sidecar to fall back
        to, which is what lets retrieval work identically on a replica whose
        filesystem never held the KB directory.
        """
        raise_error_if_astra_cloud_disable_component(astra_error_msg)
        try:
            from langflow.api.utils import knowledge_base_service
        except ImportError:
            return {}

        user_uuid = self._user_uuid
        if user_uuid is None:
            return {}
        record = await knowledge_base_service.get_by_user_and_name(
            user_uuid,
            knowledge_base or self.knowledge_base,
        )
        if record is None:
            return {}
        return knowledge_base_service.record_to_metadata_dict(record)

    async def _backend_from_record(self) -> tuple[str, dict[str, Any]] | None:
        """Read ``(backend_type, backend_config)`` off the KB's database row.

        Returns ``None`` when there is no row to read — a legacy KB predating the
        record, or bare lfx with no langflow installed. A lookup that *fails* is a
        different situation and is allowed to propagate: guessing a backend after a
        database error is how vectors end up in a store nothing queries.
        """
        try:
            from langflow.api.utils import knowledge_base_service
        except ImportError:
            return None

        user_uuid = self._user_uuid
        if user_uuid is None:
            return None
        record = await knowledge_base_service.get_by_user_and_name(user_uuid, self.knowledge_base)
        if record is None:
            return None
        return record.backend_type or BackendType.CHROMA.value, record.backend_config or {}

    async def _resolve_backend_config(self) -> tuple[str, dict[str, Any]]:
        """Resolve this KB's backend from its database row.

        Ingestion and retrieval both land here, so they cannot disagree about
        where this KB's vectors live. A backend that cannot be resolved raises
        rather than defaulting to local storage: guessing is how a pod ends up
        writing vectors to a local directory while queries follow the real config
        to a remote store and silently find nothing.
        """
        resolved = await self._backend_from_record()
        if resolved is None:
            msg = (
                f"Cannot determine the vector-store backend for knowledge base "
                f"'{self.knowledge_base}': it has no database record. Refusing to fall "
                f"back to local storage, which would write to a different store than "
                f"queries read from. If this knowledge base predates database-backed "
                f"metadata, adopt it with 'langflow reconcile-kb-from-disk'."
            )
            raise ValueError(msg)
        return resolved

    def _resolve_model_selection(self, metadata: dict[str, Any]) -> list[dict[str, Any]]:
        """Resolve the ``get_embeddings``-compatible model selection from metadata."""
        model_selection = metadata.get("model_selection")
        if model_selection:
            selection_list = [model_selection] if isinstance(model_selection, dict) else list(model_selection)
            return [self._hydrate_model_metadata(entry) for entry in selection_list]

        embedding_model_name = metadata.get("embedding_model")
        embedding_provider = metadata.get("embedding_provider", "Unknown")
        if not embedding_model_name:
            msg = (
                f"Knowledge base '{self.knowledge_base}' has no embedding model recorded; "
                "re-create it with a supported embedding model."
            )
            raise ValueError(msg)

        match = self._find_catalog_entry(embedding_model_name)
        if match is None:
            msg = (
                f"Embedding model '{embedding_model_name}' (provider '{embedding_provider}') "
                "recorded for this knowledge base is no longer available in the model registry. "
                "Please re-create the knowledge base with a supported embedding model."
            )
            raise ValueError(msg)
        return [match]

    def _hydrate_model_metadata(self, entry: dict[str, Any]) -> dict[str, Any]:
        """Fill in ``metadata.embedding_class`` / ``param_mapping`` if missing."""
        entry_metadata = entry.get("metadata") or {}
        has_class = bool(entry_metadata.get("embedding_class"))
        has_mapping = bool(entry_metadata.get("param_mapping"))
        if has_class and has_mapping:
            return entry

        model_name = entry.get("name")
        if not model_name:
            return entry

        catalog_entry = self._find_catalog_entry(model_name)
        if catalog_entry is None:
            return entry

        catalog_metadata = catalog_entry.get("metadata") or {}
        merged_metadata = {**catalog_metadata, **entry_metadata}
        return {**entry, "metadata": merged_metadata}

    def _find_catalog_entry(self, model_name: str) -> dict[str, Any] | None:
        """Look up an embedding model by name in the unified-models catalog."""
        options = get_embedding_model_options(user_id=self.user_id)
        return next((o for o in options if o.get("name") == model_name), None)

    async def retrieve_data(self) -> DataFrame:
        """Retrieve data from the selected knowledge base.

        Annotation narrowed to ``DataFrame`` to keep this output's handle
        type list at ``["Table"]`` only; widening to a union surfaces
        ``["Table", "JSON"]`` on the API and breaks every starter-project
        edge whose sourceHandle was stored against a single-type handle
        (BUG-02). The cross-mode defensive fallback may still return a
        ``Data`` at runtime — Python ignores return annotations, so
        nothing breaks.
        """
        if not _is_retrieve_mode(getattr(self, "mode", MODE_INGEST)):
            return await self.build_kb_info()
        raise_error_if_astra_cloud_disable_component(astra_error_msg)

        # Lazy import: langflow's user/DB models aren't part of lfx's
        # standalone install, so ``lfx run <starter>.json`` can't resolve
        # this symbol at module import time. Deferring to use keeps the
        # component importable in both environments.
        from langflow.services.database.models.user.crud import get_user_by_id

        async with session_scope() as db:
            if not self.user_id:
                msg = "User ID is required for fetching Knowledge Base data."
                raise ValueError(msg)
            current_user = await get_user_by_id(db, self.user_id)
            if not current_user:
                msg = f"User with ID {self.user_id} not found."
                raise ValueError(msg)
            kb_user = current_user.username

        metadata = await self._get_kb_metadata()
        if not metadata:
            msg = f"Metadata not found for knowledge base: {self.knowledge_base}. Ensure it has been indexed."
            raise ValueError(msg)

        model_selection = self._resolve_model_selection(metadata)
        chunk_size = metadata.get("chunk_size")

        # Resolve where this KB lives before instantiating embeddings: path
        # containment is a cheap local check, and a request that will be refused
        # shouldn't first pay for a credential lookup and a provider client.
        backend_type, backend_config = await self._resolve_backend_config()
        kb_path = self._resolve_store_path(kb_user, backend_type, backend_config)

        # ``api_key=None`` is not "no credential": ``get_embeddings`` resolves the
        # provider's key from the user's variables table and then the environment,
        # exactly as the server-side ingestion path does. The component input just
        # takes precedence when supplied.
        embedding_function = get_embeddings(
            model=model_selection,
            user_id=self.user_id,
            api_key=self.api_key if getattr(self, "api_key", None) else None,
            chunk_size=chunk_size,
        )

        backend = create_backend(
            backend_type,
            kb_name=self.knowledge_base,
            kb_path=kb_path,
            backend_config=backend_config,
            embedding_function=embedding_function,
            user_id=self.user_id,
        )
        try:
            user_metadata_filter = _parse_metadata_filter(getattr(self, "metadata_filter", None))
            use_scores = bool(self.search_query)
            search_k = self.top_k * 4 if user_metadata_filter else self.top_k
            results = await backend.similarity_search(
                query=self.search_query or "",
                k=search_k,
                with_scores=use_scores,
            )
            if user_metadata_filter:
                results = [
                    (doc, score) for doc, score in results if _chunk_matches_filter(doc.metadata, user_metadata_filter)
                ]
                results = results[: self.top_k]

            embeddings_by_key: dict[tuple[str, str], list[float]] = {}
            if self.include_embeddings and results:
                # Join each retrieved chunk to its stored embedding. We key on
                # ``_id`` when present and fall back to page content otherwise,
                # so KBs populated by direct file upload — whose chunks carry no
                # ``_id`` — still resolve. See ``_embedding_match_key``.
                wanted_keys = {_embedding_match_key(doc.page_content, doc.metadata) for doc, _score in results}
                async for batch in backend.iter_documents(include_embeddings=True):
                    for entry in batch:
                        if entry.embedding is None:
                            continue
                        key = _embedding_match_key(entry.content, entry.metadata)
                        if key in wanted_keys:
                            embeddings_by_key[key] = entry.embedding
                    if len(embeddings_by_key) == len(wanted_keys):
                        break

            data_list: list[Data] = []
            for doc, score in results:
                kwargs: dict[str, Any] = {"content": doc.page_content}
                if use_scores:
                    kwargs["_score"] = -1 * score
                if self.include_metadata:
                    kwargs.update(doc.metadata)
                if self.include_embeddings:
                    kwargs["_embeddings"] = embeddings_by_key.get(_embedding_match_key(doc.page_content, doc.metadata))
                data_list.append(Data(**kwargs))

            return DataFrame(data=data_list)
        finally:
            await backend.teardown()


def _embedding_match_key(content: str, metadata: dict[str, Any] | None) -> tuple[str, str]:
    """Build a stable key for aligning a retrieved chunk with its stored embedding.

    Embeddings are gathered separately (via ``iter_documents``) and then joined
    back onto the search results. Component-driven ingestion stamps a
    content-hash ``_id`` on every chunk, but direct file-upload ingestion
    (``KBIngestionHelper.perform_ingestion``) does not. Keying the join purely on
    ``_id`` therefore left every upload-populated KB with ``_embeddings: None``.

    We prefer ``_id`` when present (so legitimately distinct chunks that happen to
    share text aren't collapsed) and fall back to the chunk's page content
    otherwise. The content fallback is exact for the embedding use case: two
    chunks with identical text necessarily share the same embedding vector. The
    leading ``"id"`` / ``"content"`` tag namespaces the two key spaces so a mixed
    KB (some chunks with ``_id``, some without) never cross-matches.
    """
    doc_id = metadata.get("_id") if metadata else None
    if doc_id:
        return ("id", str(doc_id))
    return ("content", content or "")


def _parse_metadata_filter(raw: str | None) -> dict[str, list[str]]:
    """Decode the ``metadata_filter`` input into a {key: [values]} map.

    Empty or malformed input maps to an empty filter so retrieval falls back
    to the unfiltered path. JSON errors are swallowed here rather than raised:
    surfacing component-config errors at the canvas node would break a flow
    run for what is meant to be an optional refinement.
    """
    if not raw:
        return {}
    text = raw.strip() if isinstance(raw, str) else raw
    if not text:
        return {}
    try:
        decoded = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        logger.warning("KnowledgeComponent: metadata_filter is not valid JSON; ignoring filter.")
        return {}
    if not isinstance(decoded, dict):
        logger.warning("KnowledgeComponent: metadata_filter must be a JSON object; ignoring filter.")
        return {}
    result: dict[str, list[str]] = {}
    for key, value in decoded.items():
        if not isinstance(key, str):
            continue
        if isinstance(value, list):
            result[key] = [str(entry) for entry in value]
        else:
            result[key] = [str(value)]
    return result


def _chunk_matches_filter(metadata: dict[str, Any] | None, filt: dict[str, list[str]]) -> bool:
    """AND across keys, OR within key values, mirroring the chunks endpoint."""
    if not filt:
        return True
    if not metadata:
        return False
    raw = metadata.get("source_metadata")
    if not raw:
        return False
    try:
        stored = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError:
        return False
    if not isinstance(stored, dict):
        return False
    for key, expected_values in filt.items():
        actual = stored.get(key)
        if actual is None:
            return False
        actual_set = {str(entry) for entry in actual} if isinstance(actual, list) else {str(actual)}
        if not actual_set & set(expected_values):
            return False
    return True
