"""MemoryBase service — CRUD and session state management.

Ingestion orchestration, KB path helpers, and embedding inference are in
separate modules (ingestion.py, kb_path_helpers.py, embedding_helpers.py)
to keep this file focused on data access and business-rule enforcement.

Edge cases handled:
- Name uniqueness per user: 409 if a Memory Base with the same name already exists.
- Deletion during sync: cancels active tasks before DB deletion.
- KB deletion on delete: removes the associated KB directory from disk.
- Concurrent task prevention: returns 409 if a job is already IN_PROGRESS.
- Threshold updates: deferred; does not re-evaluate pending count immediately.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from lfx.base.knowledge_bases.backends import is_local_chroma
from lfx.base.knowledge_bases.backends.naming import ensure_storage_routing_allowed
from lfx.base.knowledge_bases.backends.postgres import resolve_default_kb_backend
from lfx.base.knowledge_bases.validation import validate_collection_name
from lfx.base.models.provider_registry import is_api_key_optional, provider_name_for_id, resolve_provider_id
from lfx.base.models.unified_models import get_api_key_for_provider
from lfx.base.models.unified_models.class_registry import EMBEDDING_PROVIDER_CLASS_MAPPING
from lfx.services.model_provider_policy import (
    ModelProviderPolicyPurpose,
    aresolve_model_provider_policy,
    require_model_provider,
)
from sqlmodel import col, select

from langflow.api.utils.kb_helpers import local_chroma_rejection_reason, resolve_embedding_selection
from langflow.services.base import Service
from langflow.services.database.models.memory_base.model import (
    MemoryBase,
    MemoryBaseCreate,
    MemoryBasePreprocessingOutput,
    MemoryBaseSession,
    MemoryBaseUpdate,
    MessageIngestionRecord,
)
from langflow.services.database.models.message.model import MessageTable
from langflow.services.deps import session_scope
from langflow.services.memory_base.embedding_helpers import infer_embedding_provider, infer_llm_provider
from langflow.services.memory_base.ingestion import (
    cancel_active_jobs,
)
from langflow.services.memory_base.ingestion import (
    check_mismatch as _check_mismatch,
)
from langflow.services.memory_base.ingestion import (
    on_flow_output as _on_flow_output,
)
from langflow.services.memory_base.ingestion import (
    purge_session_data as _purge_session_data,
)
from langflow.services.memory_base.ingestion import (
    regenerate as _regenerate,
)
from langflow.services.memory_base.ingestion import (
    trigger_ingestion as _trigger_ingestion,
)
from langflow.services.memory_base.kb_path_helpers import (
    BackendProvisioningError,
    delete_kb,
    initialize_kb,
    resolve_kb_username,
    sanitize_kb_name,
)
from langflow.services.memory_base.provider_scope import (
    resolve_owned_memory_flow,
)
from langflow.services.model_provider_policy_scope import scoped_model_provider_policy_for_flow

if TYPE_CHECKING:
    from lfx.services.authorization.base import ResourceVisibilityScope
    from sqlmodel.ext.asyncio.session import AsyncSession


class PreprocessingValidationError(ValueError):
    """Raised when preprocessing is enabled but the provider API key is absent."""


class EmbeddingProviderValidationError(ValueError):
    """Raised when the caller-selected embedding provider cannot serve embeddings."""


def _require_preprocessing_model_provider(user_id: uuid.UUID, preproc_model: str | None) -> str | None:
    """Require CONFIGURE access for a supplied preprocessing model identity."""
    provider = _infer_preprocessing_model_provider(preproc_model)
    if provider is None:
        return None
    require_model_provider(
        user_id=user_id,
        provider=provider,
        purpose=ModelProviderPolicyPurpose.CONFIGURE,
    )
    return provider


def _infer_preprocessing_model_provider(preproc_model: str | None) -> str | None:
    """Resolve a supplied preprocessing model without accessing credentials."""
    if not preproc_model:
        return None
    try:
        return infer_llm_provider(preproc_model)
    except ValueError as exc:
        raise PreprocessingValidationError(str(exc)) from exc


# ``get_embedding_provider`` reports this sentinel for a knowledge_base row whose
# ``model_selection`` carries no provider; it must never be authorized or persisted.
_UNKNOWN_PROVIDER = "Unknown"


def _select_embedding_provider(embedding_provider: str | None, embedding_model: str) -> str:
    """Return the canonical embedding provider for a Memory Base.

    The caller's explicit selection wins. It is canonicalized through the provider
    registry so the persisted value is the exact key every downstream embedding
    lookup uses (``EMBEDDING_PROVIDER_CLASS_MAPPING`` is matched verbatim, while the
    policy layer matches case- and alias-insensitively): ``"openai"`` becomes
    ``"OpenAI"`` and ``"IBM watsonx.ai"`` becomes ``"IBM WatsonX"``. Names the
    registry does not know are kept as supplied so the policy layer can reject
    them. Name-based inference is the fallback only when nothing usable was given.
    """
    supplied = (embedding_provider or "").strip()
    if not supplied or supplied == _UNKNOWN_PROVIDER:
        return infer_embedding_provider(embedding_model)
    return provider_name_for_id(resolve_provider_id(supplied)) or supplied


def _require_embedding_class(provider: str) -> None:
    """Reject a caller-selected provider that cannot serve embeddings.

    Runs after the policy preflight on create only. The OSS policy allows every
    provider name, so without this check a typo or a chat-only provider would be
    persisted and fail at the first ingestion with a misleading credential error.
    Stored providers on existing Memory Bases are not re-checked so an uninstalled
    bundle never blocks deactivating or renaming a Memory Base.

    Raises:
        EmbeddingProviderValidationError: ``provider`` has no registered embedding class.
    """
    if provider not in EMBEDDING_PROVIDER_CLASS_MAPPING:
        msg = f"Embedding provider '{provider}' is not available for embeddings."
        raise EmbeddingProviderValidationError(msg)


async def _preflight_memory_provider_configuration(
    *,
    flow,
    actor_user_id: uuid.UUID,
    actor_is_superuser: bool,
    embedding_model: str,
    embedding_provider: str | None,
    preproc_model: str | None,
) -> tuple[str | None, str]:
    """Authorize selected configuration providers before any owner credential read.

    ``embedding_provider`` is the provider the caller actually selected and is
    authoritative when supplied. Name-based inference is only the fallback: it
    cannot see live-discovered models (an OpenAI-Compatible endpoint's catalog is
    per-user), so guessing from the model name labels those models as OpenAI and
    every later credential lookup asks for the wrong key.
    """
    preprocessing_provider = _infer_preprocessing_model_provider(preproc_model)
    selected_embedding_provider = _select_embedding_provider(embedding_provider, embedding_model)
    providers = list(
        dict.fromkeys(provider for provider in (preprocessing_provider, selected_embedding_provider) if provider)
    )
    with scoped_model_provider_policy_for_flow(
        flow,
        user_id=actor_user_id,
        is_superuser=actor_is_superuser,
    ):
        provider_policy = await aresolve_model_provider_policy(
            user_id=actor_user_id,
            providers=providers,
            purpose=ModelProviderPolicyPurpose.CONFIGURE,
        )
        for provider in providers:
            provider_policy.require(provider)
    return preprocessing_provider, selected_embedding_provider


def _validate_preprocessing_api_key(user_id: uuid.UUID, preproc_model: str | None) -> None:
    """Raise PreprocessingValidationError if the preprocessing provider API key is missing."""
    provider = _require_preprocessing_model_provider(user_id, preproc_model)
    _validate_preprocessing_provider_api_key(user_id, preproc_model, provider)


def _validate_preprocessing_provider_api_key(
    owner_user_id: uuid.UUID,
    preproc_model: str | None,
    provider: str | None,
) -> None:
    """Validate an owner's credential after the actor's provider preflight succeeds."""
    if provider is None:
        return
    if provider == "Ollama" or is_api_key_optional(provider):
        return
    api_key = get_api_key_for_provider(owner_user_id, provider)
    if not api_key:
        msg = (
            f"No API key found for provider '{provider}' (required for preprocessing model "
            f"'{preproc_model}'). Add the key to your global variables before enabling preprocessing."
        )
        raise PreprocessingValidationError(msg)


async def _create_kb_record_for_memory_base(
    *,
    user_id: uuid.UUID,
    kb_name: str,
    embedding_provider: str,
    embedding_model: str,
    backend_type: str,
    backend_config: dict,
) -> uuid.UUID:
    """Persist the ``knowledge_base`` row backing a Memory Base.

    Memory Bases used to exist only as a directory plus a sidecar file, so their
    vector-store backend could not be resolved on a replica that had never
    touched that directory — every read path fell back to local Chroma. This row
    is now the single source of truth: embedding config, backend, cached stats,
    and the ``source_types=["memory"]`` marker all live here, so Memory Bases are
    first-class Knowledge Bases with no dependency on local disk (no sidecar is
    written at all).
    """
    from langflow.api.utils import knowledge_base_service

    record = await knowledge_base_service.create_record(
        user_id=user_id,
        name=kb_name,
        model_selection={"name": embedding_model, "provider": embedding_provider},
        backend_type=backend_type,
        backend_config=backend_config,
        source_types=["memory"],
    )
    return record.id


class MemoryBaseService(Service):
    """Service layer for MemoryBase CRUD and session state management."""

    name = "memory_base_service"

    # ------------------------------------------------------------------ #
    #  CRUD                                                                #
    # ------------------------------------------------------------------ #

    async def create(
        self,
        payload: MemoryBaseCreate,
        user_id: uuid.UUID,
        *,
        is_superuser: bool = False,
    ) -> MemoryBase:
        """Validate the owned flow and providers before provisioning a Memory Base and its KB."""
        backend_type = payload.backend_type or resolve_default_kb_backend()
        backend_config = payload.backend_config or {}

        # 0. Local Chroma is a dev-profile-only backend — its vectors live on the
        # serving box's filesystem. ``BackendProvisioningError`` is already mapped
        # to 422 by the route, which is the same status the KB endpoint returns
        # for this rejection.
        rejection = local_chroma_rejection_reason(backend_type, backend_config, resource="memory base")
        if rejection is not None:
            raise BackendProvisioningError(rejection)
        # Raises ``StorageRoutingNotAllowedError``, which the route maps to 403.
        ensure_storage_routing_allowed(backend_config, is_superuser=is_superuser)

        # 1. Verify that the referenced flow belongs to this user.
        async with session_scope() as db:
            flow = await resolve_owned_memory_flow(db, flow_id=payload.flow_id, user_id=user_id)

        # 1b. Validate every supplied preprocessing identity even while the
        # feature is disabled; enabling it additionally requires credentials.
        # Resolve and authorize every supplied provider before reading any
        # owner credential. This prevents a later embedding denial from
        # becoming a preprocessing-secret oracle.
        preprocessing_provider, embedding_provider = await _preflight_memory_provider_configuration(
            flow=flow,
            actor_user_id=user_id,
            actor_is_superuser=is_superuser,
            embedding_model=payload.embedding_model,
            embedding_provider=payload.embedding_provider,
            preproc_model=payload.preproc_model,
        )
        # Policy first so a hidden provider stays indistinguishable from a missing one.
        if (payload.embedding_provider or "").strip():
            _require_embedding_class(embedding_provider)
        if payload.preprocessing:
            _validate_preprocessing_provider_api_key(
                user_id,
                payload.preproc_model,
                preprocessing_provider,
            )

        # 2. Resolve username — needed for the KB path.
        async with session_scope() as db:
            kb_username = await resolve_kb_username(db, user_id)

        # 2b. Reject a duplicate Memory Base name BEFORE provisioning anything.
        # The authoritative uniqueness guard is the insert in step 5, but running
        # this pre-check first means the common duplicate case never provisions a
        # vector collection or writes a knowledge_base row that would then have to
        # be rolled back (and, for a remote backend, leak a live collection).
        async with session_scope() as db:
            existing = await db.exec(
                select(MemoryBase).where(MemoryBase.user_id == user_id).where(MemoryBase.name == payload.name)
            )
            if existing.first() is not None:
                msg = f"A Memory Base named '{payload.name}' already exists for this user"
                raise ValueError(msg)

        # 3. Auto-generate kb_name: sanitized_name_<8hex>
        kb_name = f"{sanitize_kb_name(payload.name)}_{uuid.uuid4().hex[:8]}"
        validate_collection_name(
            kb_name,
            resource="Memory Base",
            local=is_local_chroma(backend_type, backend_config),
        )

        # 4-5. Provision the backing KB (vector-store collection + ``knowledge_base``
        # row) then insert the memory_base row. These span independent sessions and
        # a remote collection, so there is no single DB transaction to lean on: if
        # anything after provisioning fails — a concurrent create winning the
        # unique-name race, any IntegrityError — run compensating cleanup so we
        # never leak an orphaned knowledge_base row + provisioned collection (the
        # DB row is the source of truth, so an orphan is worse than the old sidecar).
        from sqlalchemy.exc import IntegrityError

        created_kb_id: uuid.UUID | None = None
        try:
            # ``initialize_kb`` raises ``BackendProvisioningError`` for a non-local
            # backend whose connectivity check fails, so a bad remote config is
            # rejected here rather than producing a silently-dead Memory Base.
            await initialize_kb(
                kb_name=kb_name,
                kb_username=kb_username,
                user_id=user_id,
                backend_type=backend_type,
                backend_config=backend_config,
            )
            # Only a successfully created identity belongs to this attempt.
            # Failed creation must never clean up another record by name.
            created_kb_id = await _create_kb_record_for_memory_base(
                user_id=user_id,
                kb_name=kb_name,
                embedding_provider=embedding_provider,
                embedding_model=payload.embedding_model,
                backend_type=backend_type,
                backend_config=backend_config,
            )

            async with session_scope() as db:
                # Re-check inside the insert path to narrow the TOCTOU window with
                # the pre-check; the DB unique constraint is the final arbiter.
                existing = await db.exec(
                    select(MemoryBase).where(MemoryBase.user_id == user_id).where(MemoryBase.name == payload.name)
                )
                if existing.first() is not None:
                    msg = f"A Memory Base named '{payload.name}' already exists for this user"
                    raise ValueError(msg)

                mb = MemoryBase(
                    # ``backend_type``/``backend_config``/``embedding_provider`` live
                    # on the knowledge_base row created above, not on this table.
                    **payload.model_dump(exclude={"user_id", "backend_type", "backend_config", "embedding_provider"}),
                    user_id=user_id,
                    kb_name=kb_name,
                )
                db.add(mb)
                try:
                    await db.commit()
                except IntegrityError:
                    msg = f"A Memory Base named '{payload.name}' already exists for this user"
                    raise ValueError(msg) from None
                await db.refresh(mb)
        except Exception:
            if created_kb_id is not None:
                await self._cleanup_orphaned_provisioning(
                    kb_record_id=created_kb_id, kb_name=kb_name, kb_username=kb_username
                )
            raise

        return mb

    async def _cleanup_orphaned_provisioning(self, *, kb_record_id: uuid.UUID, kb_name: str, kb_username: str) -> None:
        """Compensating cleanup when a create fails after KB provisioning.

        Delete only the identity created by this attempt. The storage protocol
        retains routing on failure, and a reused name cannot redirect cleanup.
        """
        from lfx.log.logger import logger

        from langflow.api.utils import knowledge_base_service

        try:
            await knowledge_base_service.delete_record(kb_record_id)
        except Exception as exc:  # noqa: BLE001 — rollback is best-effort
            await logger.awarning("Create rollback: knowledge_base row cleanup failed for kb_name=%s: %s", kb_name, exc)
            return
        await delete_kb(kb_name=kb_name, kb_username=kb_username)

    async def list_for_user(self, user_id: uuid.UUID) -> list[MemoryBase]:
        """List Memory Bases owned by the specified user."""
        async with session_scope() as db:
            stmt = select(MemoryBase).where(MemoryBase.user_id == user_id)
            result = await db.exec(stmt)
            return list(result.all())

    def list_for_user_stmt(
        self,
        user_id: uuid.UUID,
        flow_id: uuid.UUID | None = None,
        *,
        visibility: ResourceVisibilityScope | None = None,
    ):  # type: ignore[return]
        """Return the SQLModel select statement for pagination at the API layer."""
        stmt = select(MemoryBase)
        if visibility is None:
            stmt = stmt.where(MemoryBase.user_id == user_id)
        else:
            from langflow.services.authorization.listing import restrict_to_owned_or_visible_scope

            # MemoryBase has no canonical workspace/project columns, so
            # domain-only grants intentionally remain owner-scoped.
            stmt = restrict_to_owned_or_visible_scope(
                stmt,
                id_column=MemoryBase.id,
                owner_clause=MemoryBase.user_id == user_id,
                visibility=visibility,
            )
        if flow_id is not None:
            stmt = stmt.where(MemoryBase.flow_id == flow_id)
        return stmt

    async def get(self, memory_base_id: uuid.UUID, user_id: uuid.UUID) -> MemoryBase | None:
        """Read a Memory Base only when it belongs to the specified user."""
        async with session_scope() as db:
            stmt = select(MemoryBase).where(MemoryBase.id == memory_base_id).where(MemoryBase.user_id == user_id)
            result = await db.exec(stmt)
            return result.first()

    async def update(
        self,
        memory_base_id: uuid.UUID,
        owner_user_id: uuid.UUID,
        patch: MemoryBaseUpdate,
        *,
        actor_user_id: uuid.UUID,
        actor_is_superuser: bool = False,
    ) -> MemoryBase | None:
        """Update mutable fields.

        ``owner_user_id`` scopes resource and credential access, while
        ``actor_user_id`` and ``actor_is_superuser`` identify the principal
        whose provider permission is evaluated.

        Threshold changes take effect on the NEXT auto-capture trigger; any
        already-running ingestion task ignores the change (immutable args).
        """
        async with session_scope() as db:
            stmt = select(MemoryBase).where(MemoryBase.id == memory_base_id).where(MemoryBase.user_id == owner_user_id)
            result = await db.exec(stmt)
            mb = result.first()
            if mb is None:
                return None

            flow = await resolve_owned_memory_flow(db, flow_id=mb.flow_id, user_id=owner_user_id)
            # The embedding provider chosen at create time is persisted on the
            # backing knowledge_base row (the memory_base table stores only the
            # model name). Re-inferring it from that name would relabel a
            # live-discovered model — e.g. one served by an OpenAI-Compatible
            # endpoint — as OpenAI and authorize the wrong provider.
            stored_embedding_provider, _stored_embedding_model = await resolve_embedding_selection(
                user_id=owner_user_id,
                kb_name=mb.kb_name,
            )
            preprocessing_provider, _embedding_provider = await _preflight_memory_provider_configuration(
                flow=flow,
                actor_user_id=actor_user_id,
                actor_is_superuser=actor_is_superuser,
                embedding_model=mb.embedding_model,
                embedding_provider=stored_embedding_provider,
                preproc_model=mb.preproc_model if mb.preprocessing else None,
            )

            if mb.preprocessing:
                _validate_preprocessing_provider_api_key(
                    owner_user_id,
                    mb.preproc_model,
                    preprocessing_provider,
                )

            for field, value in patch.model_dump(exclude_unset=True).items():
                setattr(mb, field, value)
            db.add(mb)
            await db.commit()
            await db.refresh(mb)
            return mb

    async def delete(self, memory_base_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Keep the Memory identity and history until storage deletion succeeds."""
        from sqlalchemy import and_

        from langflow.services.database.models.knowledge_base import KnowledgeBaseRecord
        from langflow.services.knowledge_base_storage.runtime import delete_storage_for_record

        async with session_scope() as db:
            stmt = (
                select(MemoryBase, KnowledgeBaseRecord)
                .outerjoin(
                    KnowledgeBaseRecord,
                    and_(
                        KnowledgeBaseRecord.user_id == MemoryBase.user_id,
                        KnowledgeBaseRecord.name == MemoryBase.kb_name,
                    ),
                )
                .where(MemoryBase.id == memory_base_id)
                .where(MemoryBase.user_id == user_id)
            )
            identity = (await db.exec(stmt)).first()
            if identity is None:
                return False
            mb, kb_record = identity
            kb_name = mb.kb_name
            kb_record_id = kb_record.id if kb_record is not None else None
            kb_username = await resolve_kb_username(db, user_id)
            await cancel_active_jobs(memory_base_id=memory_base_id, db=db)
            # Commit job cancellation without removing the retryable identity.
            await db.commit()

        # A provider or filesystem failure leaves both rows in place. Repeating
        # this request can finish a durable deleting/deleted storage operation.
        if kb_record is not None:
            await delete_storage_for_record(kb_record)

        async with session_scope() as db:
            mb = await db.get(MemoryBase, memory_base_id)
            # Names may have been reused by a concurrent delete/create. Only
            # remove the immutable identity captured with this Memory Base.
            kb = await db.get(KnowledgeBaseRecord, kb_record_id) if kb_record_id is not None else None
            if mb is not None:
                await db.delete(mb)
            if kb is not None:
                await db.delete(kb)
            await db.commit()
        await delete_kb(kb_name=kb_name, kb_username=kb_username)
        return True

    # ------------------------------------------------------------------ #
    #  Sessions                                                            #
    # ------------------------------------------------------------------ #

    async def verify_ownership(self, memory_base_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Raise ValueError if the Memory Base does not belong to user_id."""
        async with session_scope() as db:
            await self.get_memory_base_or_404(db, memory_base_id, user_id)

    def session_raw_messages_stmt(self, memory_base_id: uuid.UUID, session_id: str | None = None):  # type: ignore[return]
        """Statement for paginating raw ingested messages for a non-preprocessing MB.

        INNER JOIN — only messages actually ingested into this MB are returned.
        ``session_id`` denormalized on ``MessageIngestionRecord`` is immutable, so
        no extra ``MessageTable.session_id`` filter is needed.

        When ``session_id`` is ``None``, all messages ingested into the MB are
        returned, sorted by timestamp descending across sessions.

        Caller (the controller) verifies MB ownership before invoking — keeping
        ownership in the API layer where ``CurrentActiveUser`` is materialized.
        """
        from sqlalchemy import and_

        join_conditions = [
            MessageIngestionRecord.message_id == MessageTable.id,
            MessageIngestionRecord.memory_base_id == memory_base_id,
        ]
        if session_id is not None:
            join_conditions.append(MessageIngestionRecord.session_id == session_id)

        return (
            select(MessageTable, MessageIngestionRecord)
            .join(MessageIngestionRecord, and_(*join_conditions))
            .order_by(col(MessageTable.timestamp).desc())
        )

    def session_preprocessed_outputs_stmt(  # type: ignore[return]
        self, memory_base_id: uuid.UUID, session_id: str | None = None
    ):
        """Statement for paginating preprocessed (LLM-distilled) outputs.

        Used in place of ``session_raw_messages_stmt`` when ``mb.preprocessing``
        is True — for those MBs the KB stores the LLM output, not the raw rows.
        Only ``ingested`` rows are returned; ``processed`` rows are not yet in
        the KB and ``skipped`` rows have no content to surface.

        When ``session_id`` is ``None``, all ingested outputs for the MB are
        returned, sorted by ``created_at`` descending across sessions.
        """
        stmt = (
            select(MemoryBasePreprocessingOutput)
            .where(MemoryBasePreprocessingOutput.memory_base_id == memory_base_id)
            .where(MemoryBasePreprocessingOutput.status == "ingested")
        )
        if session_id is not None:
            stmt = stmt.where(MemoryBasePreprocessingOutput.session_id == session_id)
        return stmt.order_by(col(MemoryBasePreprocessingOutput.created_at).desc())

    def sessions_stmt(self, memory_base_id: uuid.UUID, user_id: uuid.UUID):  # type: ignore[return]
        """Return the select statement for persisted sessions, for use with apaginate.

        Inline-joins MemoryBase to verify ownership in the SQL itself, so a
        caller that forgets a pre-check cannot leak other users' sessions.
        """
        return (
            select(MemoryBaseSession)
            .join(MemoryBase, MemoryBase.id == MemoryBaseSession.memory_base_id)
            .where(MemoryBaseSession.memory_base_id == memory_base_id)
            .where(MemoryBase.user_id == user_id)
            .order_by(col(MemoryBaseSession.last_sync_at).desc())
        )

    # ------------------------------------------------------------------ #
    #  Ingestion delegation                                                #
    # ------------------------------------------------------------------ #

    async def trigger_ingestion(
        self,
        memory_base_id: uuid.UUID,
        owner_user_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        session_id: str,
    ) -> str:
        """Authorize and enqueue ingestion for one Memory Base conversation."""
        return await _trigger_ingestion(
            memory_base_id,
            owner_user_id,
            actor_user_id,
            session_id,
            get_mb_or_raise=self.get_memory_base_or_404,
            get_or_create_session=self._get_or_create_session,
        )

    async def on_flow_output(
        self,
        flow_id: uuid.UUID,
        session_id: str,
        job_id: uuid.UUID | None,
    ) -> None:
        """Capture eligible flow output into the associated Memory Base session."""
        await _on_flow_output(
            flow_id,
            session_id,
            job_id,
            get_or_create_session=self._get_or_create_session,
        )

    async def check_mismatch(self, memory_base_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Check whether the owner-scoped Memory Base embedding configuration has drifted."""
        return await _check_mismatch(
            memory_base_id,
            user_id,
            get_mb_or_raise=self.get_memory_base_or_404,
        )

    async def regenerate(
        self,
        memory_base_id: uuid.UUID,
        owner_user_id: uuid.UUID,
        actor_user_id: uuid.UUID,
    ) -> list[str]:
        """Authorize and enqueue regeneration of the Memory Base sessions."""
        return await _regenerate(
            memory_base_id,
            owner_user_id,
            actor_user_id,
            get_mb_or_raise=self.get_memory_base_or_404,
            trigger_ingestion_fn=self.trigger_ingestion,
        )

    async def purge_session_data(self, user_id: uuid.UUID, session_ids: list[str], *, db=None) -> int:
        """Remove Chroma chunks and tracking rows for the given sessions.

        Called when the user deletes session messages from the UI so that the
        ingested embeddings don't leak into newly-created sessions. Scoped to
        the caller's Memory Bases — never touches another user's data.
        """
        return await _purge_session_data(user_id=user_id, session_ids=session_ids, db=db)

    # ------------------------------------------------------------------ #
    #  Public query helpers                                                #
    # ------------------------------------------------------------------ #

    async def get_memory_base_or_404(
        self, db: AsyncSession, memory_base_id: uuid.UUID, user_id: uuid.UUID
    ) -> MemoryBase:
        """Fetch a MemoryBase or raise ValueError (mapped to 404 at the API layer)."""
        stmt = select(MemoryBase).where(MemoryBase.id == memory_base_id).where(MemoryBase.user_id == user_id)
        result = await db.exec(stmt)
        mb = result.first()
        if mb is None:
            msg = f"MemoryBase {memory_base_id} not found"
            raise ValueError(msg)
        return mb

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    async def _get_or_create_session(
        self, db: AsyncSession, memory_base_id: uuid.UUID, session_id: str
    ) -> MemoryBaseSession:
        """Find or initialize the processing cursor for a Memory Base conversation."""
        stmt = (
            select(MemoryBaseSession)
            .where(MemoryBaseSession.memory_base_id == memory_base_id)
            .where(MemoryBaseSession.session_id == session_id)
        )
        result = await db.exec(stmt)
        mbs = result.first()
        if mbs is None:
            mbs = MemoryBaseSession(memory_base_id=memory_base_id, session_id=session_id)
            db.add(mbs)
            await db.commit()
            await db.refresh(mbs)
        return mbs
