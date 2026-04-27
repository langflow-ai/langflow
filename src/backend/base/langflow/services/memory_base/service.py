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

from sqlmodel import col, select

from langflow.services.base import Service
from langflow.services.database.models.memory_base.model import (
    MemoryBase,
    MemoryBaseCreate,
    MemoryBaseSession,
    MemoryBaseUpdate,
)
from langflow.services.deps import session_scope
from langflow.services.memory_base.embedding_helpers import infer_embedding_provider
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
    regenerate as _regenerate,
)
from langflow.services.memory_base.ingestion import (
    trigger_ingestion as _trigger_ingestion,
)
from langflow.services.memory_base.kb_path_helpers import (
    delete_kb,
    initialize_kb,
    resolve_kb_username,
    sanitize_kb_name,
)

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession


class MemoryBaseService(Service):
    """Service layer for MemoryBase CRUD and session state management."""

    name = "memory_base_service"

    # ------------------------------------------------------------------ #
    #  CRUD                                                                #
    # ------------------------------------------------------------------ #

    async def create(self, payload: MemoryBaseCreate, user_id: uuid.UUID) -> MemoryBase:
        # 1. Verify that the referenced flow belongs to this user.
        async with session_scope() as db:
            from langflow.services.database.models.flow.model import Flow

            flow_result = await db.exec(select(Flow).where(Flow.id == payload.flow_id).where(Flow.user_id == user_id))
            if flow_result.first() is None:
                msg = f"Flow {payload.flow_id} not found"
                raise PermissionError(msg)

        # 2. Resolve username — needed for the KB path.
        async with session_scope() as db:
            kb_username = await resolve_kb_username(db, user_id)

        # 3. Auto-generate kb_name: sanitized_name_<8hex>
        kb_name = f"{sanitize_kb_name(payload.name)}_{uuid.uuid4().hex[:8]}"

        # 4. Create KB directory and embedding_metadata.json on disk.
        embedding_provider = infer_embedding_provider(payload.embedding_model)
        await initialize_kb(
            kb_name=kb_name,
            kb_username=kb_username,
            embedding_provider=embedding_provider,
            embedding_model=payload.embedding_model,
        )

        # 5. Uniqueness check + insert.
        from sqlalchemy.exc import IntegrityError

        async with session_scope() as db:
            existing = await db.exec(
                select(MemoryBase).where(MemoryBase.user_id == user_id).where(MemoryBase.name == payload.name)
            )
            if existing.first() is not None:
                msg = f"A Memory Base named '{payload.name}' already exists for this user"
                raise ValueError(msg)

            mb = MemoryBase(
                **payload.model_dump(exclude={"user_id"}),
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

        return mb

    async def list_for_user(self, user_id: uuid.UUID) -> list[MemoryBase]:
        async with session_scope() as db:
            stmt = select(MemoryBase).where(MemoryBase.user_id == user_id)
            result = await db.exec(stmt)
            return list(result.all())

    def list_for_user_stmt(self, user_id: uuid.UUID, flow_id: uuid.UUID | None = None):  # type: ignore[return]
        """Return the SQLModel select statement for pagination at the API layer."""
        stmt = select(MemoryBase).where(MemoryBase.user_id == user_id)
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
        user_id: uuid.UUID,
        patch: MemoryBaseUpdate,
    ) -> MemoryBase | None:
        """Update mutable fields.

        Threshold changes take effect on the NEXT auto-capture trigger; any
        already-running ingestion task ignores the change (immutable args).
        """
        async with session_scope() as db:
            stmt = select(MemoryBase).where(MemoryBase.id == memory_base_id).where(MemoryBase.user_id == user_id)
            result = await db.exec(stmt)
            mb = result.first()
            if mb is None:
                return None
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
        user_id: uuid.UUID,
        session_id: str,
    ) -> str:
        return await _trigger_ingestion(
            memory_base_id,
            user_id,
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

    async def regenerate(self, memory_base_id: uuid.UUID, user_id: uuid.UUID) -> list[str]:
        return await _regenerate(
            memory_base_id,
            user_id,
            get_mb_or_raise=self.get_memory_base_or_404,
            trigger_ingestion_fn=self.trigger_ingestion,
        )

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
