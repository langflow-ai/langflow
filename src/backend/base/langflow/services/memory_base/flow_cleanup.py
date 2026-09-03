"""Reclaim a flow's Memory Bases when the flow itself is deleted.

A Memory Base is owned by exactly one flow (``memory_base.flow_id``), and is
meant to die with it. There is no DB-level foreign key from ``memory_base`` to
``flow`` — the vector-store collection that backs each Memory Base lives outside
the database and can only be torn down with an explicit call — so the cascade is
coordinated here in code rather than by the schema. This module is the single
entry point invoked from ``cascade_delete_flow`` so *every* flow-deletion path
(single delete, bulk delete, project delete, and the flow runner's state resets)
reclaims the Memory Bases and their remote collections.

The work is split into two deliberately-separated phases:

* :func:`purge_flow_memory_bases` runs **inside** the flow-deletion transaction,
  on the caller's session. It removes every ``memory_base`` row (and its
  children) plus the backing ``knowledge_base`` row, so the database cleanup is
  atomic with the flow deletion — if the flow deletion rolls back, so does this.
  It captures the handles needed to reach each remote collection *before*
  dropping the ``knowledge_base`` rows that carry the backend routing config,
  and returns them for the second phase.
* :func:`finalize_flow_memory_base_cleanup` runs the best-effort **external**
  teardown (remote vector-store collection, then the local Chroma directory).
  It must run only after the flow-deletion transaction has committed — deleting
  a remote collection for a flow that then survives a rolled-back transaction
  would be worse than leaving the collection in place. It never raises: a broken
  connection to the remote store is logged (the collection is left for manual
  cleanup) exactly as standalone Memory Base deletion behaves.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from lfx.base.knowledge_bases.backends import create_backend, is_local_chroma
from lfx.log.logger import logger
from sqlalchemy import delete
from sqlmodel import col, select

from langflow.api.utils.kb_helpers import _coerce_backend_config_value
from langflow.services.database.models.knowledge_base.model import KnowledgeBaseRecord
from langflow.services.database.models.memory_base.model import (
    MemoryBase,
    MemoryBasePreprocessingOutput,
    MemoryBaseSession,
    MemoryBaseWorkflowRun,
    MessageIngestionRecord,
)
from langflow.services.database.models.user.model import User
from langflow.services.memory_base.ingestion import cancel_active_jobs
from langflow.services.memory_base.kb_path_helpers import delete_kb

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession


@dataclass(frozen=True)
class FlowMemoryBaseCleanup:
    """External resources of one deleted Memory Base, captured before its rows go.

    The ``knowledge_base`` row carries the backend routing (``backend_type`` /
    ``backend_config``) needed to reach a remote collection, and the row is
    dropped inside the flow-deletion transaction — so everything the external
    teardown needs is snapshotted here first.
    """

    kb_name: str
    user_id: UUID
    # ``None`` when the owning user could not be resolved (e.g. the user is being
    # deleted in the same transaction); the on-disk path cannot be built without
    # it, so local-Chroma disk cleanup is skipped in that case.
    kb_username: str | None
    backend_type: str
    backend_config: dict = field(default_factory=dict)


async def purge_flow_memory_bases(session: AsyncSession, flow_id: UUID) -> list[FlowMemoryBaseCleanup]:
    """Delete the DB rows for every Memory Base owned by ``flow_id``.

    Runs on the caller's session so the deletions commit (or roll back) together
    with the flow deletion. Removes the ``memory_base`` rows, their child rows
    (sessions, workflow runs, ingestion records, preprocessing outputs) and the
    backing ``knowledge_base`` rows. The child deletes are explicit because
    SQLite does not honor ``ON DELETE CASCADE`` unless ``PRAGMA foreign_keys`` is
    on — matching the surrounding ``cascade_delete_flow`` convention.

    Returns one :class:`FlowMemoryBaseCleanup` per Memory Base so the caller can
    run :func:`finalize_flow_memory_base_cleanup` after the transaction commits.
    No external I/O happens here.
    """
    memory_bases = list((await session.exec(select(MemoryBase).where(MemoryBase.flow_id == flow_id))).all())
    if not memory_bases:
        return []

    # Resolve each owner's username once (KB directories are laid out under it).
    username_cache: dict[UUID, str | None] = {}

    async def _resolve_username(user_id: UUID) -> str | None:
        if user_id not in username_cache:
            username_cache[user_id] = (await session.exec(select(User.username).where(User.id == user_id))).first()
        return username_cache[user_id]

    handles: list[FlowMemoryBaseCleanup] = []
    kb_record_ids: list[UUID] = []
    for mb in memory_bases:
        # Cancel in-flight ingestion so a running job cannot write to a
        # collection we are about to drop. Best-effort — never let job teardown
        # block the flow deletion.
        try:
            await cancel_active_jobs(memory_base_id=mb.id, db=session)
        except Exception as exc:  # noqa: BLE001 — job teardown is best-effort
            await logger.awarning(
                "Could not cancel ingestion jobs for Memory Base %s during flow deletion: %s", mb.id, exc
            )

        # Snapshot backend routing from the knowledge_base row BEFORE it is
        # deleted below — the remote teardown in phase two needs it.
        kb_record = (
            await session.exec(
                select(KnowledgeBaseRecord)
                .where(KnowledgeBaseRecord.user_id == mb.user_id)
                .where(KnowledgeBaseRecord.name == mb.kb_name)
            )
        ).first()
        if kb_record is not None:
            backend_type = kb_record.backend_type or "chroma"
            backend_config = _coerce_backend_config_value(kb_record.backend_config)
            kb_record_ids.append(kb_record.id)
        else:
            # No row to resolve a remote backend from; treat as local so the
            # only cleanup attempted is the on-disk directory (a no-op if absent).
            backend_type = "chroma"
            backend_config = {}

        handles.append(
            FlowMemoryBaseCleanup(
                kb_name=mb.kb_name,
                user_id=mb.user_id,
                kb_username=await _resolve_username(mb.user_id),
                backend_type=backend_type,
                backend_config=backend_config,
            )
        )

    memory_base_ids = [mb.id for mb in memory_bases]

    # Children first (explicit — SQLite does not enforce FK cascades), then the
    # memory_base rows, then the backing knowledge_base rows.
    await session.exec(
        delete(MessageIngestionRecord).where(col(MessageIngestionRecord.memory_base_id).in_(memory_base_ids))
    )
    await session.exec(
        delete(MemoryBaseWorkflowRun).where(col(MemoryBaseWorkflowRun.memory_base_id).in_(memory_base_ids))
    )
    await session.exec(
        delete(MemoryBasePreprocessingOutput).where(
            col(MemoryBasePreprocessingOutput.memory_base_id).in_(memory_base_ids)
        )
    )
    await session.exec(delete(MemoryBaseSession).where(col(MemoryBaseSession.memory_base_id).in_(memory_base_ids)))
    await session.exec(delete(MemoryBase).where(col(MemoryBase.id).in_(memory_base_ids)))
    if kb_record_ids:
        await session.exec(delete(KnowledgeBaseRecord).where(col(KnowledgeBaseRecord.id).in_(kb_record_ids)))

    return handles


async def finalize_flow_memory_base_cleanup(handles: list[FlowMemoryBaseCleanup]) -> None:
    """Drop the external resources captured by :func:`purge_flow_memory_bases`.

    Call this only after the flow-deletion transaction has committed. For each
    Memory Base it drops the remote vector-store collection (skipped for local
    Chroma, whose vectors live on disk) and then removes the local KB directory.
    Best-effort throughout: a single Memory Base's failure never aborts the rest,
    and nothing here raises.
    """
    for handle in handles:
        await _drop_remote_collection(handle)
        # Local Chroma vectors and any residual on-disk state live in the KB
        # directory; ``delete_kb`` is a no-op for a remote-backed Memory Base
        # (no directory) and when no local storage is configured.
        if handle.kb_username is not None:
            await delete_kb(kb_name=handle.kb_name, kb_username=handle.kb_username)


async def _drop_remote_collection(handle: FlowMemoryBaseCleanup) -> None:
    """Delete one Memory Base's remote vector-store collection, best-effort.

    Local Chroma is skipped — its vectors are removed with the KB directory by
    :func:`delete_kb`. For every remote backend the collection lives off-box and
    needs an explicit ``delete_collection`` call. If the store cannot be reached,
    log that the connection is broken and that the remote collection could not be
    deleted (it must then be cleaned up manually), and swallow the error so flow
    deletion is never blocked by an unreachable cluster.
    """
    if is_local_chroma(handle.backend_type, handle.backend_config):
        return

    backend = create_backend(
        handle.backend_type,
        kb_name=handle.kb_name,
        backend_config=handle.backend_config,
        user_id=handle.user_id,
    )
    try:
        await backend.ensure_ready()
        await backend.delete_collection()
    except Exception as exc:  # noqa: BLE001 — best-effort remote cleanup
        # Distinguish a broken connection (the case the requirement calls out)
        # from other delete failures so the log is actionable.
        connection_broken = True
        try:
            connection_broken = not (await backend.test_connection()).ok
        except Exception:  # noqa: BLE001 — probing the connection is itself best-effort
            connection_broken = True
        if connection_broken:
            await logger.awarning(
                "Connection to the '%s' vector store is broken: the remote collection for the deleted flow's "
                "Memory Base (kb_name=%s) could not be deleted and may need manual cleanup: %s",
                handle.backend_type,
                handle.kb_name,
                exc,
            )
        else:
            await logger.awarning(
                "Could not delete the remote '%s' collection for the deleted flow's Memory Base (kb_name=%s); "
                "it may need manual cleanup: %s",
                handle.backend_type,
                handle.kb_name,
                exc,
            )
    finally:
        await backend.teardown()
