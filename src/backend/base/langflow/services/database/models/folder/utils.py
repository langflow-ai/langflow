from typing import TYPE_CHECKING
from uuid import UUID

from sqlmodel import Session, select, update

from langflow.services.database.models.flow.model import Flow

from .constants import DEFAULT_FOLDER_DESCRIPTION, DEFAULT_FOLDER_NAME
from .model import Folder

if TYPE_CHECKING:
    pass


def create_default_folder_if_it_doesnt_exist(session: Session, user_id: UUID):
    found_folder = session.exec(select(Folder).where(Folder.user_id == user_id)).first()
    if not found_folder:
        folder = Folder(name=DEFAULT_FOLDER_NAME, user_id=user_id, description=DEFAULT_FOLDER_DESCRIPTION)
        session.add(folder)
        session.commit()
        session.refresh(folder)
        session.exec(
            update(Flow)
            .where(
                (Flow.folder_id == None)  # noqa: E711
                & (Flow.user_id == user_id)
            )
            .values(folder_id=folder.id)
        )
        session.commit()
        return folder
    else:
        return found_folder
