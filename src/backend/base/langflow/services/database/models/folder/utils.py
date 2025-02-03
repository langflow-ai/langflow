from uuid import UUID

from sqlmodel import and_, select, update
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.initial_setup.setup import get_or_create_default_folder
from langflow.services.database.models.flow.model import Flow

from .constants import DEFAULT_FOLDER_DESCRIPTION, DEFAULT_FOLDER_NAME
from .model import Folder


async def create_default_folder_if_it_doesnt_exist(session: AsyncSession, user_id: UUID):
    stmt = select(Folder).where(Folder.user_id == user_id)
    folder = (await session.exec(stmt)).first()
    if not folder:
        folder = Folder(
            name=DEFAULT_FOLDER_NAME,
            user_id=user_id,
            description=DEFAULT_FOLDER_DESCRIPTION,
        )
        session.add(folder)
        await session.commit()
        await session.refresh(folder)
        await session.exec(
            update(Flow)
            .where(
                and_(
                    Flow.folder_id is None,
                    Flow.user_id == user_id,
                )
            )
            .values(folder_id=folder.id)
        )
        await session.commit()
    return folder


async def get_default_folder_id(session: AsyncSession, user_id: UUID):
    folder = (
        await session.exec(select(Folder).where(Folder.name == DEFAULT_FOLDER_NAME, Folder.user_id == user_id))
    ).first()
    if not folder:
        folder = await get_or_create_default_folder(session, user_id)
    return folder.id
