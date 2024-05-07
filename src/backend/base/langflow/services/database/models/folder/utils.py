from typing import TYPE_CHECKING

from sqlmodel import Session, select

from .constants import DEFAULT_FOLDER_DESCRIPTION, DEFAULT_FOLDER_NAME
from .model import Folder

if TYPE_CHECKING:
    from langflow.services.database.models.user.model import User


def create_default_folder_if_it_doesnt_exist(session: Session, user: "User"):
    if not session.exec(select(Folder).where(Folder.user_id == user.id)).first():
        folder = Folder(name=DEFAULT_FOLDER_NAME, user_id=user.id, description=DEFAULT_FOLDER_DESCRIPTION)
        session.add(folder)
        session.commit()
        session.refresh(folder)
        return folder
    return None
