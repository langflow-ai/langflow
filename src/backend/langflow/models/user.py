from sqlalchemy.orm import Session
from langflow.models.user import User as DBUser
from langflow.models.base_control import BaseControl
from uuid import UUID


class User(BaseControl):
    id: UUID
    username: str
    email: str
    disabled: bool = False
    is_superuser: bool = False


def get_user(db: Session, user_id: UUID) -> User:
    db_user = db.query(DBUser).filter(DBUser.id == user_id).first()
    return User.from_orm(db_user) if db_user else None  # type: ignore
