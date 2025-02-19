from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.database.models.file.model import File


async def get_file_by_id(db: AsyncSession, file_id: UUID) -> File | None:
    if isinstance(file_id, str):
        file_id = UUID(file_id)
    stmt = select(File).where(File.id == file_id)

    return (await db.exec(stmt)).first()
