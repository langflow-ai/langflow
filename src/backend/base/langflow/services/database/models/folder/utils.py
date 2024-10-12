from uuid import UUID

from sqlmodel import Session, and_, select, update

from langflow.services.database.models.flow.model import Flow

from .constants import DEFAULT_FOLDER_DESCRIPTION, DEFAULT_FOLDER_NAME
from .model import Folder


def create_default_folder_if_it_doesnt_exist(session: Session, user_id: UUID):
    folder = session.exec(select(Folder).where(Folder.user_id == user_id)).first()
    if not folder:
        folder = Folder(
            name=DEFAULT_FOLDER_NAME,
            user_id=user_id,
            description=DEFAULT_FOLDER_DESCRIPTION,
        )
        session.add(folder)
        session.commit()
        session.refresh(folder)
        session.exec(
            update(Flow)
            .where(
                and_(
                    Flow.folder_id is None,
                    Flow.user_id == user_id,
                )
            )
            .values(folder_id=folder.id)
        )
        session.commit()
    return folder


def get_default_folder_id(session: Session, user_id: UUID):
    folder = session.exec(select(Folder).where(Folder.name == DEFAULT_FOLDER_NAME, Folder.user_id == user_id)).first()
    if not folder:
        folder = create_default_folder_if_it_doesnt_exist(session, user_id)
    return folder.id
