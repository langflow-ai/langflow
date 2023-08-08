from datetime import datetime
from sqlalchemy.orm import Session

from langflow.services.database.models.base import SQLModelSerializable, SQLModel
from sqlmodel import Field
from uuid import UUID, uuid4


class User(SQLModelSerializable, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, unique=True)
    username: str = Field(index=True, unique=True)
    password: str = Field()
    is_disabled: bool = Field(default=False)
    is_superuser: bool = Field(default=False)
    create_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class UserAddModel(SQLModel):
    username: str = Field()
    password: str = Field()
    is_disabled: bool = Field(default=False)
    is_superuser: bool = Field(default=False)


class UserListModel(SQLModel):
    id: UUID = Field(default_factory=uuid4)
    username: str = Field()
    is_disabled: bool = Field()
    is_superuser: bool = Field()
    create_at: datetime = Field()
    updated_at: datetime = Field()


def get_user(db: Session, username: str) -> User:
    db_user = db.query(User).filter(User.username == username).first()
    return User.from_orm(db_user) if db_user else None  # type: ignore
