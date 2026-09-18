from uuid import UUID

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.database.models.file.model import File


async def get_file_by_id(db: AsyncSession, file_id: UUID) -> File | None:
    if isinstance(file_id, str):
        file_id = UUID(file_id)
    stmt = select(File).where(File.id == file_id)

    return (await db.exec(stmt)).first()


async def delete_file_records(db: AsyncSession, *, file_ids: tuple[UUID, ...], actor_id: UUID) -> None:
    """Delete successful storage removals and stage policy in the caller's transaction."""
    from langflow.services.authorization.actions import FileAction
    from langflow.services.authorization.fetch import load_mutation_actor
    from langflow.services.authorization.guards import ensure_file_permission
    from langflow.services.authorization.lifecycle import stage_resource_mutation
    from langflow.services.database.lock_retry import run_with_lock_retry
    from langflow.services.deps import get_authorization_service

    if not file_ids:
        return

    async def delete_attempt(_attempt: int) -> None:
        authorization = get_authorization_service()
        await authorization.acquire_resource_mutation_lock(session=db)
        actor = await load_mutation_actor(db, actor_id)
        rows: list[File] = []
        for offset in range(0, len(file_ids), 200):
            rows.extend((await db.exec(select(File).where(col(File.id).in_(file_ids[offset : offset + 200])))).all())
        for row in rows:
            await ensure_file_permission(
                actor, FileAction.DELETE, file_id=row.id, file_user_id=row.user_id, audit_session=db
            )
        for row in rows:
            await db.delete(row)
        await db.flush()
        if rows:
            # The event follows the complete batch; the selected service reconciles once.
            await stage_resource_mutation(db, resource_type="file", resource_id=file_ids[0], deleted=True)

    await run_with_lock_retry(delete_attempt, session=db, description="delete file records")
