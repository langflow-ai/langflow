"""Memory Base retrieval component.

Queries the auto-provisioned Chroma KB backing a Memory Base, scoped to the
current flow's request session. Additional option to filter by session_id if the
developer wants to turn that on. The component will auto filter based on session_id then.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import numpy as np
from langflow.api.utils.kb_helpers import KBIngestionHelper, resolve_backend_selection, resolve_embedding_selection
from langflow.services.database.models.memory_base.model import MemoryBase
from langflow.services.database.models.user.crud import get_user_by_id
from langflow.services.memory_base.kb_path_helpers import hash_session_id, validate_kb_path
from sqlmodel import select

from lfx.base.knowledge_bases.backends import create_backend
from lfx.components.files_and_knowledge._kb_paths import (
    get_knowledge_bases_root_path,
)
from lfx.custom import Component
from lfx.io import BoolInput, DropdownInput, IntInput, MessageTextInput, Output
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.services.deps import session_scope

if TYPE_CHECKING:
    from pathlib import Path

    from langflow.services.database.models.user.model import User
    from sqlmodel.ext.asyncio.session import AsyncSession

    from lfx.base.knowledge_bases.backends.base import BaseVectorStoreBackend


def _coerce_uuid(value: Any) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


def _distance_to_similarity(distance: float) -> float:
    """Chroma returns a distance; flip the sign so larger == more similar."""
    return -1 * distance


def _to_python_scalar(value: Any) -> Any:
    """Convert numpy scalars (int64, float64, bool_, …) to Python primitives.

    Chroma persists integer/float metadata as numpy scalars, which break JSON
    serialization when this component is consumed as an Agent tool — LangChain's
    tool-output path calls ``vars()`` / iterates the value, both of which fail
    on numpy C-extension scalars. Coerce at the boundary so downstream stays
    primitive-only.
    """
    if isinstance(value, np.generic):
        return value.item()
    return value


class MemoryBaseComponent(Component):
    display_name = "Memory Base"
    description = (
        "Retrieve long-term memory from a Memory Base attached to this workflow. "
        "When 'Filter by Session' is off, queries run across all sessions."
    )
    icon = "brain"
    name = "MemoryBase"

    inputs = [
        DropdownInput(
            name="memory_base",
            display_name="Memory Base",
            info="Memory Base whose captured conversation history will be searched.",
            required=True,
            options=[],
            refresh_button=True,
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="search_query",
            display_name="Search Query",
            info="Query used for semantic retrieval against the memory base.",
            tool_mode=True,
        ),
        IntInput(
            name="top_k",
            display_name="Top K Results",
            info="Number of top results to return.",
            value=5,
            advanced=True,
            required=False,
        ),
        BoolInput(
            name="include_metadata",
            display_name="Include Metadata",
            info="Include chunk metadata (session_id, sender, timestamp, …) on each row.",
            value=True,
            advanced=True,
        ),
        BoolInput(
            name="filter_by_session",
            display_name="Filter by Session",
            info=(
                "If enabled, only memories from the current session will be retrieved. "
                "Disable to allow retrieval across every session ingested into this "
                "Memory Base (useful for cross-conversation recall)."
            ),
            value=True,
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            name="retrieve_data",
            display_name="Results",
            method="retrieve_memory",
            info=(
                "Returns matching memory chunks. Scoped to the current session by "
                "default; turn 'Filter by Session' off to retrieve across sessions."
            ),
        ),
    ]

    def _build_where_clause(self, *, session_id: str | None = None) -> dict | None:
        """Compose the metadata filter based on opt-in filters and manual params.

        Emits a flat ``{key: value}`` dict, which is the contract every
        ``BaseVectorStoreBackend`` accepts: Chroma reads it as ``$eq`` shorthand
        and OpenSearch translates it into a bool query. Chroma's explicit
        ``{"$eq": ...}`` operator form is NOT portable — a remote backend would
        treat the operator dict as a literal value and silently match nothing.
        """
        predicates: dict = {}
        # Defensive bool() — BoolInput coerces strings, but if this attribute is
        # ever overridden externally with a non-bool value, ``"false"`` would be
        # truthy and silently disable the toggle.
        if bool(self.filter_by_session) and session_id:
            predicates["session_id"] = str(session_id)

        return predicates or None

    async def update_build_config(self, build_config, field_value, field_name=None):  # noqa: ARG002
        if field_name != "memory_base":
            return build_config

        flow_id = _coerce_uuid(self._get_runtime_or_frontend_node_attr("flow_id"))
        user_uuid = _coerce_uuid(self.user_id)
        if flow_id is None or user_uuid is None:
            build_config["memory_base"]["options"] = []
            build_config["memory_base"]["value"] = None
            return build_config

        # At design time self.user_id == the flow developer == MB owner, so this
        # filters to the same set a Flow-lookup would return but without relying
        # on the Flow row being persisted yet.
        async with session_scope() as db:
            stmt = select(MemoryBase).where(
                MemoryBase.flow_id == flow_id,
                MemoryBase.user_id == user_uuid,
            )
            mbs = list((await db.exec(stmt)).all())

        options = sorted(mb.name for mb in mbs)
        build_config["memory_base"]["options"] = options
        if build_config["memory_base"].get("value") not in options:
            build_config["memory_base"]["value"] = None
        return build_config

    async def _resolve_attached_mb(
        self,
        db: AsyncSession,
        selected: str,
        flow_id: uuid.UUID,
    ) -> tuple[MemoryBase, User]:
        """Look up the MB row scoped to the current flow and resolve its owner."""
        mb = (
            await db.exec(
                select(MemoryBase).where(
                    MemoryBase.name == selected,
                    MemoryBase.flow_id == flow_id,
                )
            )
        ).first()
        if mb is None:
            msg = f"Memory Base '{selected}' is not attached to this flow."
            raise ValueError(msg)

        owner = await get_user_by_id(db, mb.user_id)
        if owner is None:
            msg = "Memory Base owner account could not be resolved."
            raise ValueError(msg)
        return mb, owner

    def _resolve_kb_location(self, owner_username: str, kb_name: str) -> Path:
        """Build and validate the on-disk KB path for the given owner."""
        kb_root = get_knowledge_bases_root_path()
        kb_path = kb_root / owner_username / kb_name
        try:
            validate_kb_path(kb_root, kb_path)
        except ValueError as exc:
            msg = "Memory Base path is not accessible."
            raise ValueError(msg) from exc
        return kb_path

    async def _build_backend(
        self,
        kb_path: Path,
        owner: User,
        kb_name: str,
    ) -> BaseVectorStoreBackend:
        """Construct the KB's configured backend, wired to its embedding function.

        Both the embedding config and the backend are resolved from the
        ``knowledge_base`` row (sidecar only as a legacy fallback), so a Memory
        Base provisioned on OpenSearch or Chroma Cloud is queried there — and with
        the right embedding model — even on a replica whose local disk never held
        the KB directory or its ``embedding_metadata.json``.
        """
        provider, model = await resolve_embedding_selection(user_id=owner.id, kb_name=kb_name, kb_path=kb_path)
        embedding_function = await KBIngestionHelper.build_embeddings(provider, model, owner)

        backend_type, backend_config = await resolve_backend_selection(
            user_id=owner.id, kb_name=kb_name, kb_path=kb_path
        )
        backend = create_backend(
            backend_type,
            kb_name=kb_name,
            kb_path=kb_path,
            backend_config=backend_config,
            embedding_function=embedding_function,
            user_id=owner.id,
        )
        await backend.ensure_ready()
        return backend

    def _format_results(self, results: list[tuple]) -> DataFrame:
        """Convert Chroma (doc, score) tuples into the component's DataFrame output.

        Metadata values are coerced from numpy scalars to Python primitives so the
        resulting DataFrame is JSON-serializable when the component is invoked as
        an Agent tool.
        """
        data_list: list[Data] = []
        for doc, score in results:
            kwargs: dict = {"content": doc.page_content}
            if self.search_query:
                kwargs["_score"] = _to_python_scalar(_distance_to_similarity(score))
            if self.include_metadata:
                for key, value in (doc.metadata or {}).items():
                    kwargs[key] = _to_python_scalar(value)
            data_list.append(Data(**kwargs))
        return DataFrame(data=data_list)

    async def retrieve_memory(self) -> DataFrame:
        """Retrieve chunks from the selected Memory Base.

        Scoped to the current ``session_id`` when ``filter_by_session`` is true; when
        false, every chunk in the Memory Base is queryable so the agent can recall
        context from prior conversations across all sessions.
        """
        session_id = getattr(self.graph, "session_id", None)
        if bool(self.filter_by_session) and not session_id:
            # Only required when filtering is on, since the value gates the where clause.
            msg = (
                "A session_id is required on the flow request when 'Filter by Session' "
                "is enabled — disable the toggle to allow cross-session retrieval."
            )
            raise ValueError(msg)

        flow_id = _coerce_uuid(getattr(self.graph, "flow_id", None))
        if flow_id is None:
            msg = "flow_id is not available on the graph context; Memory Base retrieval is unavailable."
            raise ValueError(msg)

        selected = self.memory_base
        if not selected:
            msg = "No Memory Base is selected."
            raise ValueError(msg)

        async with session_scope() as db:
            mb, owner = await self._resolve_attached_mb(db, selected, flow_id)
            owner_username = owner.username
            kb_name = mb.kb_name

        # ``kb_path`` is still needed for a local-Chroma backend (that's where its
        # vectors live), but embedding + backend now resolve from the DB row, so a
        # missing on-disk ``embedding_metadata.json`` is no longer fatal — a
        # remote-backed Memory Base is fully queryable on a replica with no local
        # KB directory.
        kb_path = self._resolve_kb_location(owner_username, kb_name)

        where = self._build_where_clause(session_id=session_id)

        logger.debug(
            "MemoryBase retrieval mb=%s session_hash=%s where=%s top_k=%s",
            selected,
            hash_session_id(session_id) if session_id else "<none>",
            where,
            self.top_k,
        )

        if not self.search_query:
            # Embedding providers may reject empty input; skip the round-trip entirely.
            return DataFrame(data=[])

        backend = await self._build_backend(kb_path, owner, kb_name)
        try:
            results = await backend.similarity_search(
                query=self.search_query,
                k=self.top_k,
                filter=where,
                with_scores=True,
            )
        finally:
            await backend.teardown()
        return self._format_results(results)
