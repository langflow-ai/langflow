"""Knowledge Base retrieval component.

Delegates to the same two abstractions ingestion uses:

* ``get_embeddings`` from ``lfx.base.models.unified_models`` resolves
  the embedding provider + API key via the user's provider settings,
  so the component stays credential-free.
* ``ChromaBackend`` from ``lfx.base.knowledge_bases.backends`` wraps
  the vector store lookup, which keeps the component working unchanged
  as MongoDB / Astra / Postgres backends land in Phase 4.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from lfx.base.knowledge_bases.backends import BackendType, create_backend
from lfx.base.knowledge_bases.knowledge_base_utils import get_knowledge_bases
from lfx.base.models.unified_models import get_embedding_model_options, get_embeddings
from lfx.custom import Component
from lfx.io import BoolInput, DropdownInput, IntInput, MessageTextInput, Output
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.services.deps import get_settings_service, session_scope
from lfx.utils.validate_cloud import raise_error_if_astra_cloud_disable_component

_KNOWLEDGE_BASES_ROOT_PATH: Path | None = None

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
        raise_error_if_astra_cloud_disable_component(astra_error_msg)
        if field_name == "knowledge_base":
            build_config["knowledge_base"]["options"] = await get_knowledge_bases(
                _get_knowledge_bases_root_path(),
                user_id=self.user_id,
            )
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
        """Load the knowledge base's embedding metadata file.

        The metadata file is the source of truth for which embedding
        model was used at ingestion time — retrieval must use the same
        model, otherwise queries are embedded into a different vector
        space.

        Legacy key material that may be present in older metadata
        files (``api_key``) is intentionally ignored here; credential
        resolution is now owned by the unified-models layer via
        provider settings.
        """
        raise_error_if_astra_cloud_disable_component(astra_error_msg)
        metadata_file = kb_path / "embedding_metadata.json"
        if not metadata_file.exists():
            logger.warning(f"Embedding metadata file not found at {metadata_file}")
            return {}

        try:
            with metadata_file.open("r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from {metadata_file}")
            return {}

    async def _resolve_backend(self, *, kb_user: str) -> tuple[str, dict[str, Any]]:  # noqa: ARG002 — reserved for path-scoped fallback
        """Return ``(backend_type, backend_config)`` for this KB.

        Prefers the DB row written at create time (Phase 1.5) so the
        configured backend (Chroma / Mongo / Astra / Postgres) is
        honored. Falls back to Chroma for legacy KBs that only exist
        on disk — those ingestions still work because the Chroma
        files live next to ``embedding_metadata.json``.
        """
        try:
            from langflow.api.utils import knowledge_base_service

            user_uuid = self._user_uuid
            if user_uuid is None:
                return BackendType.CHROMA.value, {}
            record = await knowledge_base_service.get_by_user_and_name(user_uuid, self.knowledge_base)
        except Exception as exc:  # noqa: BLE001 — service hiccups fall through to Chroma
            logger.debug("KB record lookup failed: %s", exc)
            return BackendType.CHROMA.value, {}

        if record is None:
            return BackendType.CHROMA.value, {}
        return (
            record.backend_type or BackendType.CHROMA.value,
            record.backend_config or {},
        )

    def _resolve_model_selection(self, metadata: dict[str, Any]) -> list[dict[str, Any]]:
        """Resolve the ``get_embeddings``-compatible model selection from metadata.

        New KBs persist the full ``model_selection`` dict at ingest
        time so we can pass it straight through. Older KBs only
        stored ``embedding_model`` / ``embedding_provider`` strings —
        for those we look the model up in the current unified-models
        catalog and fail loudly if it's no longer available (indicating
        the KB needs to be re-created with a supported model).
        """
        model_selection = metadata.get("model_selection")
        if model_selection:
            return [model_selection] if isinstance(model_selection, dict) else model_selection

        embedding_model_name = metadata.get("embedding_model")
        embedding_provider = metadata.get("embedding_provider", "Unknown")
        if not embedding_model_name:
            msg = (
                f"Knowledge base '{self.knowledge_base}' has no embedding model recorded; "
                "re-create it with a supported embedding model."
            )
            raise ValueError(msg)

        options = get_embedding_model_options(user_id=self.user_id)
        match = next((o for o in options if o.get("name") == embedding_model_name), None)
        if match is None:
            msg = (
                f"Embedding model '{embedding_model_name}' (provider '{embedding_provider}') "
                "recorded for this knowledge base is no longer available in the model registry. "
                "Please re-create the knowledge base with a supported embedding model."
            )
            raise ValueError(msg)
        return [match]

    async def retrieve_data(self) -> DataFrame:
        """Retrieve data from the selected knowledge base.

        Shape of the call:

        1. Resolve the KB directory on disk (scoped to the current user).
        2. Read ``embedding_metadata.json`` to learn which embedding
           model was used at ingest time.
        3. Hand that model_selection to ``get_embeddings`` so the
           unified-models layer instantiates the right provider + pulls
           the API key from the user's provider settings.
        4. Open a ``ChromaBackend`` against the KB and run the query.
        """
        raise_error_if_astra_cloud_disable_component(astra_error_msg)

        # Lazy import: langflow's user/DB models aren't part of lfx's
        # standalone install, so ``lfx run <starter>.json`` can't
        # resolve this symbol at module import time. Deferring to use
        # keeps the component importable in both environments.
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
        kb_path = _get_knowledge_bases_root_path() / kb_user / self.knowledge_base

        metadata = self._get_kb_metadata(kb_path)
        if not metadata:
            msg = f"Metadata not found for knowledge base: {self.knowledge_base}. Ensure it has been indexed."
            raise ValueError(msg)

        # Unified-models owns credential resolution: the API key, base
        # URL, and any provider-specific variables come from the
        # user's provider settings, so retrieval uses the exact same
        # code path as ingestion.
        model_selection = self._resolve_model_selection(metadata)
        chunk_size = metadata.get("chunk_size")
        embedding_function = get_embeddings(
            model=model_selection,
            user_id=self.user_id,
            chunk_size=chunk_size,
        )

        backend_type, backend_config = await self._resolve_backend(kb_user=kb_user)
        backend = create_backend(
            backend_type,
            kb_name=self.knowledge_base,
            kb_path=kb_path,
            backend_config=backend_config,
            embedding_function=embedding_function,
            # Forward for variable_service-based credential resolution on
            # Mongo/Astra/Postgres backends. Chroma ignores this.
            user_id=self.user_id,
        )
        try:
            use_scores = bool(self.search_query)
            results = await backend.similarity_search(
                query=self.search_query or "",
                k=self.top_k,
                with_scores=use_scores,
            )

            # Build an id → embedding map via the backend-agnostic iterator
            # rather than reaching into Chroma's private ``_collection`` API
            # (which Mongo/Astra/Postgres don't expose). Scoped to the KB's
            # doc ids so the pass stays bounded.
            id_to_embedding: dict[str, list[float]] = {}
            if self.include_embeddings and results:
                doc_ids = {doc.metadata.get("_id") for doc, _score in results if doc.metadata.get("_id")}
                if doc_ids:
                    async for batch in backend.iter_documents(include_embeddings=True):
                        for entry in batch:
                            doc_id = entry.metadata.get("_id")
                            if doc_id in doc_ids and entry.embedding is not None:
                                id_to_embedding[doc_id] = entry.embedding
                        if len(id_to_embedding) == len(doc_ids):
                            break

            data_list: list[Data] = []
            for doc, score in results:
                kwargs: dict[str, Any] = {"content": doc.page_content}
                if use_scores:
                    kwargs["_score"] = -1 * score
                if self.include_metadata:
                    kwargs.update(doc.metadata)
                if self.include_embeddings:
                    kwargs["_embeddings"] = id_to_embedding.get(doc.metadata.get("_id"))
                data_list.append(Data(**kwargs))

            return DataFrame(data=data_list)
        finally:
            await backend.teardown()
