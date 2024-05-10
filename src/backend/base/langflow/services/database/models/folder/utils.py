from typing import TYPE_CHECKING
from uuid import UUID

from langflow.services.database.models.flow.model import Flow
from sqlmodel import Session, select, update

from .constants import DEFAULT_FOLDER_DESCRIPTION, DEFAULT_FOLDER_NAME
from .model import Folder

if TYPE_CHECKING:
    from langflow.services.database.models.user.model import User


def create_default_folder_if_it_doesnt_exist(session: Session, user_id: UUID):
    if not session.exec(select(Folder).where(Folder.user_id == user_id)).first():
        folder = Folder(name=DEFAULT_FOLDER_NAME, user_id=user_id, description=DEFAULT_FOLDER_DESCRIPTION)
        session.add(folder)
        session.commit()
        session.refresh(folder)
        session.exec(
            update(Flow)
            .where((Flow.folder_id == None) & (Flow.user_id == user_id))
            .values(folder_id=folder.id)
        )
        session.commit()
    return None
