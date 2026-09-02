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
from lfx.base.knowledge_bases.backends.postgres import resolve_default_kb_backend
from lfx.base.knowledge_bases.validation import validate_collection_name
from lfx.base.models.provider_registry import is_api_key_optional
from lfx.base.models.unified_models import get_api_key_for_provider
from lfx.services.model_provider_policy import (
    ModelProviderPolicyPurpose,
    aresolve_model_provider_policy,
    require_model_provider,
)
from sqlmodel import col, select

from langflow.api.utils.kb_helpers import local_chroma_rejection_reason
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
    delete_kb_remote_collection,
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


async def _preflight_memory_provider_configuration(
    *,
    flow,
    actor_user_id: uuid.UUID,
    actor_is_superuser: bool,
    embedding_model: str,
    preproc_model: str | None,
) -> tuple[str | None, str]:
    """Authorize selected configuration providers before any owner credential read."""
    preprocessing_provider = _infer_preprocessing_model_provider(preproc_model)
    embedding_provider = infer_embedding_provider(embedding_model)
    providers = list(dict.fromkeys(provider for provider in (preprocessing_provider, embedding_provider) if provider))
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
    return preprocessing_provider, embedding_provider


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
) -> None:
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

    await knowledge_base_service.create_record(
        user_id=user_id,
        name=kb_name,
        model_selection={"name": embedding_model, "provider": embedding_provider},
        backend_type=backend_type,
        backend_config=backend_config,
        source_types=["memory"],
    )


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
        backend_type = payload.backend_type or resolve_default_kb_backend()
        backend_config = payload.backend_config or {}

        # 0. Local Chroma is a dev-profile-only backend — its vectors live on the
        # serving box's filesystem. ``BackendProvisioningError`` is already mapped
        # to 422 by the route, which is the same status the KB endpoint returns
        # for this rejection.
        rejection = local_chroma_rejection_reason(backend_type, backend_config, resource="memory base")
        if rejection is not None:
            raise BackendProvisioningError(rejection)

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
            preproc_model=payload.preproc_model,
        )
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

        needs_cleanup = False
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
            # From here on a collection may exist and the row will be written, so
            # any later failure must roll both back.
            needs_cleanup = True
            await _create_kb_record_for_memory_base(
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
                    # ``backend_type``/``backend_config`` live on the knowledge_base
                    # row created above, not on this table.
                    **payload.model_dump(exclude={"user_id", "backend_type", "backend_config"}),
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
            if needs_cleanup:
                await self._cleanup_orphaned_provisioning(kb_name=kb_name, kb_username=kb_username, user_id=user_id)
            raise

        return mb

    async def _cleanup_orphaned_provisioning(self, *, kb_name: str, kb_username: str, user_id: uuid.UUID) -> None:
        """Compensating cleanup when a create fails after KB provisioning.

        Mirrors :meth:`delete`'s teardown order — remote collection first (it
        needs the ``knowledge_base`` row to resolve backend config), then the
        row, then local disk — so a rejected create leaves nothing behind.
        Best-effort and idempotent: each step no-ops when there is nothing to
        remove.
        """
        from lfx.log.logger import logger

        from langflow.api.utils import knowledge_base_service

        try:
            await delete_kb_remote_collection(kb_name=kb_name, user_id=user_id)
        except Exception as exc:  # noqa: BLE001 — rollback is best-effort
            await logger.awarning("Create rollback: remote collection cleanup failed for kb_name=%s: %s", kb_name, exc)
        try:
            await knowledge_base_service.delete_by_user_and_name(user_id, kb_name)
        except Exception as exc:  # noqa: BLE001 — rollback is best-effort
            await logger.awarning("Create rollback: knowledge_base row cleanup failed for kb_name=%s: %s", kb_name, exc)
        await delete_kb(kb_name=kb_name, kb_username=kb_username)

    async def list_for_user(self, user_id: uuid.UUID) -> list[MemoryBase]:
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
            preprocessing_provider, _embedding_provider = await _preflight_memory_provider_configuration(
                flow=flow,
                actor_user_id=actor_user_id,
                actor_is_superuser=actor_is_superuser,
                embedding_model=mb.embedding_model,
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
        """Delete a MemoryBase and its associated KB directory."""
        async with session_scope() as db:
            stmt = select(MemoryBase).where(MemoryBase.id == memory_base_id).where(MemoryBase.user_id == user_id)
            result = await db.exec(stmt)
            mb = result.first()
            if mb is None:
                return False

            kb_name = mb.kb_name
            kb_username = await resolve_kb_username(db, user_id)

            # Cancel active ingestion jobs before removing the DB record
            await cancel_active_jobs(memory_base_id=memory_base_id, db=db)

            await db.delete(mb)
            await db.commit()

        # Drop the remote vector-store collection FIRST, while the
        # knowledge_base row (and its backend config) still exists — otherwise
        # the OpenSearch index / Chroma Cloud collection is stranded with no way
        # to resolve how to reach it. Best-effort; local Chroma is a no-op here
        # (its vectors are removed by ``delete_kb`` below).
        await delete_kb_remote_collection(kb_name=kb_name, user_id=user_id)

        # Delete the backing knowledge_base row — it's the authoritative record for
        # this Memory Base, so leaving it would orphan the row (and keep the KB's
        # memory-base guards active for a name the user just freed). Best-effort:
        # the memory_base row is already committed.
        from langflow.api.utils import knowledge_base_service

        try:
            await knowledge_base_service.delete_by_user_and_name(user_id, kb_name)
        except Exception:  # noqa: BLE001
            from lfx.log.logger import logger

            await logger.awarning("Could not delete knowledge_base row for Memory Base kb_name=%s", kb_name)

        # Delete the corresponding KB from disk (best-effort — DB already committed)
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
        await _on_flow_output(
            flow_id,
            session_id,
            job_id,
            get_or_create_session=self._get_or_create_session,
        )

    async def check_mismatch(self, memory_base_id: uuid.UUID, user_id: uuid.UUID) -> bool:
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
        return await _regenerate(
            memory_base_id,
            owner_user_id,
            actor_user_id,
            get_mb_or_raise=self.get_memory_base_or_404,
            trigger_ingestion_fn=self.trigger_ingestion,
        )

    async def purge_session_data(self, user_id: uuid.UUID, session_ids: list[str]) -> int:
        """Remove Chroma chunks and tracking rows for the given sessions.

        Called when the user deletes session messages from the UI so that the
        ingested embeddings don't leak into newly-created sessions. Scoped to
        the caller's Memory Bases — never touches another user's data.
        """
        return await _purge_session_data(user_id=user_id, session_ids=session_ids)

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
