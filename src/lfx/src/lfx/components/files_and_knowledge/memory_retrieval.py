"""Memory Base retrieval component.

Queries the vector store backing a Memory Base, scoped to the current flow's
request session. Additional option to filter by session_id if the developer wants
to turn that on. The component will auto filter based on session_id then.

Where that store lives comes from the Memory Base's ``knowledge_base`` row, not
from disk: only a local-Chroma Memory Base resolves a filesystem path at all.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

import numpy as np
from langflow.api.utils.kb_helpers import (
    resolve_backend_selection,
    resolve_embedding_selection,
    resolve_local_store_path,
)
from langflow.services.database.models.memory_base.model import MemoryBase
from langflow.services.database.models.user.crud import get_user_by_id
from langflow.services.memory_base.kb_path_helpers import hash_session_id
from sqlmodel import select

from lfx.base.knowledge_bases.backends import create_backend
from lfx.custom import Component
from lfx.io import BoolInput, DropdownInput, IntInput, MessageTextInput, Output
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.services.deps import session_scope
from lfx.workflow.end_user_identity import end_user_id_from_scoped_session, serving_end_user_enabled

if TYPE_CHECKING:
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


def _session_filter_enabled(value: Any) -> bool:
    """Parse serialized false values while keeping unknown values fail-closed."""
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "no", "off"}
    return bool(value)


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

    async def _policy_embedding_selection(self, selected: str) -> tuple[str, str]:
        """Resolve an attached Memory Base's non-secret embedding metadata."""
        flow_id = _coerce_uuid(self._get_runtime_or_frontend_node_attr("flow_id"))
        if flow_id is None:
            msg = "flow_id is not available on the graph context; Memory Base retrieval is unavailable."
            raise ValueError(msg)

        owner_user_id = _coerce_uuid(self.user_id)
        if owner_user_id is None:
            msg = "user_id is not available on the graph context; Memory Base retrieval is unavailable."
            raise ValueError(msg)

        async with session_scope() as db:
            memory_base = (
                await db.exec(
                    select(MemoryBase).where(
                        MemoryBase.name == selected,
                        MemoryBase.flow_id == flow_id,
                        MemoryBase.user_id == owner_user_id,
                    )
                )
            ).first()
        if memory_base is None:
            msg = f"Memory Base '{selected}' is not attached to this flow."
            raise ValueError(msg)
        return await resolve_embedding_selection(user_id=memory_base.user_id, kb_name=memory_base.kb_name)

    async def _additional_model_provider_policy_ids(self, purpose, parameters=None) -> tuple[str, ...]:
        """Discover the persisted embedding provider before runtime input hydration."""
        from lfx.base.models.provider_registry import resolve_provider_id
        from lfx.services.model_provider_policy import ModelProviderPolicyError

        effective_parameters = parameters if isinstance(parameters, Mapping) else getattr(self, "_parameters", None)
        if not isinstance(effective_parameters, Mapping):
            effective_parameters = {}
        selected = effective_parameters.get("memory_base", getattr(self, "memory_base", None))
        if not isinstance(selected, str) or not selected.strip():
            return ()

        provider, _model = await self._policy_embedding_selection(selected.strip())
        if not isinstance(provider, str) or not provider.strip():
            unknown_provider = "unknown"
            raise ModelProviderPolicyError(unknown_provider, purpose)
        return (resolve_provider_id(provider),)

    async def arequire_model_provider_policy(self, purpose, *, user_id=None, parameters=None) -> None:
        """Capture the trusted actor context after the shared pre-hydration gate."""
        await super().arequire_model_provider_policy(
            purpose,
            user_id=user_id,
            parameters=parameters,
        )

        from lfx.services.model_provider_policy import current_model_provider_policy_context

        actor_user_id = self.user_id if user_id is None else user_id
        policy_context = current_model_provider_policy_context()
        self._runtime_provider_policy_actor_id = actor_user_id
        self._runtime_provider_policy_attributes = (
            dict(policy_context.attributes)
            if policy_context is not None and str(policy_context.user_id) == str(actor_user_id)
            else {}
        )

    def _build_where_clause(self, *, session_id: str | None = None, end_user_id: str | None = None) -> dict | None:
        """Compose the metadata filter based on opt-in filters and manual params.

        Emits a flat ``{key: value}`` dict, which is the contract every
        ``BaseVectorStoreBackend`` accepts: Chroma reads it as ``$eq`` shorthand
        and OpenSearch translates it into a bool query. Chroma's explicit
        ``{"$eq": ...}`` operator form is NOT portable — a remote backend would
        treat the operator dict as a literal value and silently match nothing.

        When ``filter_by_session`` is on, the session-id predicate already scopes to one
        end user (its ``<end_user>::<base>`` prefix). When it is off (cross-session recall)
        on the serving plane, ``end_user_id`` keeps the query within that one end user so it
        does not span every end user's chunks in the shared service-account store. Off /
        editor (``end_user_id`` None) adds neither predicate — all sessions, unchanged.
        """
        predicates: dict = {}
        if _session_filter_enabled(self.filter_by_session) and session_id:
            predicates["session_id"] = str(session_id)
        elif end_user_id:
            predicates["end_user_id"] = str(end_user_id)

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
        execution_user_id: uuid.UUID,
    ) -> tuple[MemoryBase, User]:
        """Look up the MB row scoped to the exact flow execution principal."""
        mb = (
            await db.exec(
                select(MemoryBase).where(
                    MemoryBase.name == selected,
                    MemoryBase.flow_id == flow_id,
                    MemoryBase.user_id == execution_user_id,
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

    async def _build_backend(
        self,
        owner: User,
        owner_username: str,
        kb_name: str,
    ) -> BaseVectorStoreBackend:
        """Construct the KB's configured backend, wired to its embedding function.

        The embedding config and the backend both resolve from the
        ``knowledge_base`` row, so nothing on disk is consulted to decide *where*
        this Memory Base lives. A local path is then derived only when that row
        says local Chroma; for OpenSearch, pgVector, or Chroma Cloud it stays
        ``None`` and the filesystem is never touched. That is what lets a
        Memory Base be queried — with the right embedding model — from a replica
        whose local disk never held the KB directory.
        """
        # Re-resolve the persisted selection and actor policy immediately before
        # owner credential access. The graph-level preflight runs before input
        # hydration; this repeat also closes a metadata-change race between that
        # boundary and backend construction.
        provider, model = await resolve_embedding_selection(user_id=owner.id, kb_name=kb_name)
        provider_policy = await self._resolve_runtime_embedding_policy(provider, owner.id)

        # Resolve where this Memory Base lives before constructing a provider
        # client. Path containment and backend metadata do not read embedding
        # credentials.
        backend_type, backend_config = await resolve_backend_selection(user_id=owner.id, kb_name=kb_name)
        try:
            kb_path = resolve_local_store_path(
                kb_name,
                owner_username,
                backend_type=backend_type,
                backend_config=backend_config,
            )
        except ValueError as exc:
            msg = "Memory Base path is not accessible."
            raise ValueError(msg) from exc

        embedding_function = self._build_embeddings_with_policy(
            provider,
            model,
            owner_user_id=owner.id,
            provider_policy=provider_policy,
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

    async def _resolve_runtime_embedding_policy(self, provider: str, owner_user_id: uuid.UUID):
        """Refresh actor-scoped provider policy before owner credential lookup."""
        from lfx.services.model_provider_policy import (
            ModelProviderPolicyPurpose,
            aresolve_model_provider_policy,
            current_model_provider_policy_context,
        )

        actor_user_id = getattr(self, "_runtime_provider_policy_actor_id", None)
        attributes = getattr(self, "_runtime_provider_policy_attributes", None)
        if actor_user_id is None:
            policy_context = current_model_provider_policy_context()
            if policy_context is not None:
                actor_user_id = policy_context.user_id
                attributes = dict(policy_context.attributes)
            else:
                actor_user_id = owner_user_id
                attributes = {}

        snapshot = await aresolve_model_provider_policy(
            user_id=actor_user_id,
            providers=[provider],
            purpose=ModelProviderPolicyPurpose.USE,
            attributes=attributes,
        )
        snapshot.require(provider)
        return snapshot

    @staticmethod
    def _build_embeddings_with_policy(provider: str, model: str, *, owner_user_id, provider_policy):
        """Build with owner credentials while reusing the actor's trusted decision."""
        from lfx.base.models.unified_models import get_embeddings
        from lfx.base.models.unified_models.class_registry import (
            EMBEDDING_PARAM_MAPPINGS,
            EMBEDDING_PROVIDER_CLASS_MAPPING,
        )

        embedding_class = EMBEDDING_PROVIDER_CLASS_MAPPING.get(provider)
        param_mapping = EMBEDDING_PARAM_MAPPINGS.get(provider)
        if not embedding_class or not param_mapping:
            msg = f"Embedding provider '{provider}' is not registered"
            raise ValueError(msg)
        selected_option = {
            "name": model,
            "provider": provider,
            "category": provider,
            "icon": provider,
            "metadata": {
                "embedding_class": embedding_class,
                "param_mapping": param_mapping,
                "model_type": "embeddings",
            },
        }
        return get_embeddings(
            model=[selected_option],
            user_id=owner_user_id,
            provider_policy=provider_policy,
        )

    def _format_results(self, results: list[tuple], backend: BaseVectorStoreBackend) -> DataFrame:
        """Convert backend ``(doc, score)`` tuples into the component's DataFrame output.

        Metadata values are coerced from numpy scalars to Python primitives so the
        resulting DataFrame is JSON-serializable when the component is invoked as
        an Agent tool.
        """
        data_list: list[Data] = []
        for doc, score in results:
            kwargs: dict = {"content": doc.page_content}
            if self.search_query:
                kwargs["_score"] = _to_python_scalar(backend.normalize_score(score))
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
        filter_on = _session_filter_enabled(self.filter_by_session)
        if filter_on and not session_id:
            # Only required when filtering is on, since the value gates the where clause.
            msg = (
                "A session_id is required on the flow request when 'Filter by Session' "
                "is enabled — disable the toggle to allow cross-session retrieval."
            )
            raise ValueError(msg)

        # Serving plane: the end-user id lives in the scoped session prefix. When filtering
        # by session it is already scoped; when doing cross-session recall it becomes the
        # sole end-user predicate (see _build_where_clause).
        end_user_id = end_user_id_from_scoped_session(session_id)
        if serving_end_user_enabled() and not filter_on and end_user_id is None:
            # Fail-closed: an anonymous serving caller has no end-user scope, so
            # cross-session recall over the shared service-account store would return every
            # end user's memory. Anonymous runs persist nothing and have no cross-session
            # memory to recall, so return empty rather than leak.
            logger.debug("MemoryBase cross-session recall blocked for anonymous serving caller")
            return DataFrame(data=[])

        flow_id = _coerce_uuid(getattr(self.graph, "flow_id", None))
        if flow_id is None:
            msg = "flow_id is not available on the graph context; Memory Base retrieval is unavailable."
            raise ValueError(msg)

        execution_user_id = _coerce_uuid(getattr(self.graph, "user_id", None))
        if execution_user_id is None:
            msg = "user_id is not available on the graph context; Memory Base retrieval is unavailable."
            raise ValueError(msg)

        selected = self.memory_base
        if not selected:
            msg = "No Memory Base is selected."
            raise ValueError(msg)

        async with session_scope() as db:
            mb, owner = await self._resolve_attached_mb(db, selected, flow_id, execution_user_id)
            owner_username = owner.username
            kb_name = mb.kb_name

        where = self._build_where_clause(session_id=session_id, end_user_id=end_user_id)

        logger.debug(
            "MemoryBase retrieval mb=%s session_hash=%s session_filter=%s top_k=%s",
            selected,
            hash_session_id(session_id) if session_id else "<none>",
            where is not None,
            self.top_k,
        )

        if not self.search_query:
            # Embedding providers may reject empty input; skip the round-trip entirely.
            return DataFrame(data=[])

        backend = await self._build_backend(owner, owner_username, kb_name)
        try:
            results = await backend.similarity_search(
                query=self.search_query,
                k=self.top_k,
                filter=where,
                with_scores=True,
            )
        finally:
            await backend.teardown()
        return self._format_results(results, backend)
