"""Builder erase: knowledge bases, one per call, including their remote collection and local directory."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.log.logger import logger
from lfx.utils.util_strings import escape_like_pattern
from sqlmodel import and_, col, not_, or_, select

from langflow.services.data_subjects.batching import delete_batch
from langflow.services.data_subjects.export import LIKE_ESCAPE
from langflow.services.database.models.knowledge_base.model import KnowledgeBaseRecord
from langflow.services.database.models.knowledge_base_storage_migration import KnowledgeBaseStorageMigration
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_job_service
from langflow.services.knowledge_base_storage.legacy_directories import LegacyDirectories, is_owner_folder
from langflow.services.knowledge_base_storage.retained import is_source_identity

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.sql.elements import ColumnElement
    from sqlmodel.ext.asyncio.session import AsyncSession
    from sqlmodel.sql.expression import SelectOfScalar

    from langflow.services.data_subjects.context import EraseContext


async def erase_knowledge_bases(session: AsyncSession, ctx: EraseContext) -> int:
    # The KB delete route's own path: drain writers, fence and delete the store, then the row.
    # A store that cannot be reached raises, so the step is retried and holds the request open.
    from langflow.api.utils import knowledge_base_service
    from langflow.api.v1 import knowledge_bases as kb_routes

    record = (
        await session.exec(
            select(KnowledgeBaseRecord).where(KnowledgeBaseRecord.user_id == ctx.subject_user_id).limit(1)
        )
    ).first()
    if record is None:
        return 0
    await kb_routes._cancel_inflight_ingestion_for_kb(  # noqa: SLF001
        kb_name=record.name, asset_id=record.id, job_service=get_job_service()
    )
    await knowledge_base_service.delete_record(record.id)
    return 1


def _other_accounts_bases(subject_user_id: UUID) -> SelectOfScalar[UUID]:
    return select(KnowledgeBaseRecord.id).where(KnowledgeBaseRecord.user_id != subject_user_id)


def builder_upgrade_runs(subject_user_id: UUID, username: str) -> ColumnElement[bool]:
    """Ledger rows of the builder's bases. They outlive the base and name its `<username>/<name>` directory.

    The name is the owner's at upgrade time, so a row is also matched by a base the builder owns. A row
    under this name is not the builder's when someone else owns its base now, after a rename, or when it
    is older than the builder's account, so a former holder of the name made it.
    """
    prefix = f"{escape_like_pattern(username)}/%"
    run_kb_id = col(KnowledgeBaseStorageMigration.kb_id)
    owned = select(KnowledgeBaseRecord.id).where(KnowledgeBaseRecord.user_id == subject_user_id)
    joined = select(User.create_at).where(User.id == subject_user_id).scalar_subquery()
    by_name = and_(
        col(KnowledgeBaseStorageMigration.source_identity).like(prefix, escape=LIKE_ESCAPE),
        run_kb_id.not_in(_other_accounts_bases(subject_user_id)),
        col(KnowledgeBaseStorageMigration.created_at) >= joined,
    )
    return or_(by_name, run_kb_id.in_(owned))


async def builder_directories(
    session: AsyncSession,
    subject_user_id: UUID,
    username: str,
    *,
    named: set[str],
    kb_ids: set[UUID],
    found: LegacyDirectories,
) -> set[str]:
    """The legacy `<owner>/<name>` directories that hold the builder's bases.

    A directory keeps the name its owner had when it was written, and a username can change and be taken
    again, so the folder alone does not say whose it is. As in adoption, a directory is tied to a base by
    a ledger row, by the owner and name of a Chroma base's row, or by the base id its sidecar records.
    ``named`` holds the directories that the builder's ledger rows and rows name, and ``kb_ids`` the
    builder's bases. The files a deletion left in the builder's folder are a deleted base's, so they are
    the builder's too. A directory is the builder's when one of these ties it to the builder and none ties
    it to another account. A path that is not one `<owner>/<name>` directory as written, one under an internal
    folder such as `.migration`, or a directory that could not be read is left alone, since it may be
    another account's.
    """
    candidates = {
        source for source in named if is_source_identity(source) and is_owner_folder(source.partition("/")[0])
    }
    candidates |= {source for source, kb_id in found.recorded.items() if kb_id in kb_ids}
    candidates |= {source for source in found.tombstones if source.startswith(f"{username}/")}
    readable = {source for source in candidates if found.readable(source)}
    if dropped := len(named - candidates) + len(candidates - readable):
        await logger.awarning(
            "op=data_subject_erase kept %d knowledge base directories it could not attribute", dropped
        )
    if not readable:
        return set()
    # Another account's base, or a run that is not the builder's, ties the directory to someone else.
    by_ledger = set(
        (
            await session.exec(
                select(KnowledgeBaseStorageMigration.source_identity).where(
                    col(KnowledgeBaseStorageMigration.source_identity).in_(readable),
                    not_(builder_upgrade_runs(subject_user_id, username)),
                )
            )
        ).all()
    )
    foreign = {found.recorded[source] for source in readable if source in found.recorded} - kb_ids
    others = _other_accounts_bases(subject_user_id).where(col(KnowledgeBaseRecord.id).in_(foreign))
    taken = set((await session.exec(others)).all()) if foreign else set()
    by_sidecar = {source for source in readable if found.recorded.get(source) in taken}
    return readable - by_ledger - by_sidecar


async def erase_knowledge_base_upgrades(session: AsyncSession, ctx: EraseContext) -> int:
    owner = await session.get(User, ctx.subject_user_id)
    if owner is None:
        return 0
    return await delete_batch(
        session, KnowledgeBaseStorageMigration, builder_upgrade_runs(ctx.subject_user_id, owner.username)
    )
