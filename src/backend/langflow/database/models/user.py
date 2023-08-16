from sqlmodel import Field
from uuid import UUID, uuid4
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
from datetime import timezone, datetime
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, Depends

from langflow.services.utils import get_session
from langflow.services.database.models.base import SQLModelSerializable, SQLModel


class User(SQLModelSerializable, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, unique=True)
    username: str = Field(index=True, unique=True)
    password: str = Field()
    is_active: bool = Field(default=False)
    is_superuser: bool = Field(default=False)
    create_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login_at: Optional[datetime] = Field()


class UserAddModel(SQLModel):
    username: str = Field()
    password: str = Field()


class UserListModel(SQLModel):
    id: UUID = Field(default_factory=uuid4)
    username: str = Field()
    is_active: bool = Field()
    is_superuser: bool = Field()
    create_at: datetime = Field()
    updated_at: datetime = Field()
    last_login_at: Optional[datetime] = Field()


class UserPatchModel(SQLModel):
    username: Optional[str] = Field()
    is_active: Optional[bool] = Field()
    is_superuser: Optional[bool] = Field()
    last_login_at: Optional[datetime] = Field()


class UsersResponse(BaseModel):
    total_count: int
    users: List[UserListModel]


def get_user_by_username(db: Session, username: str) -> User:
    db_user = db.query(User).filter(User.username == username).first()
    return User.from_orm(db_user) if db_user else None  # type: ignore


def get_user_by_id(db: Session, id: UUID) -> User:
    db_user = db.query(User).filter(User.id == id).first()
    return User.from_orm(db_user) if db_user else None  # type: ignore


def update_user(
    user_id: UUID, user: UserPatchModel, db: Session = Depends(get_session)
) -> User:
    user_db = get_user_by_username(db, user.username)  # type: ignore
    if user_db and user_db.id != user_id:
        raise HTTPException(status_code=409, detail="Username already exists")

    user_db = get_user_by_id(db, user_id)
    if not user_db:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        user_data = user.dict(exclude_unset=True)
        for key, value in user_data.items():
            setattr(user_db, key, value)

        user_db.updated_at = datetime.now(timezone.utc)
        user_db = db.merge(user_db)
        db.commit()
        if db.identity_key(instance=user_db) is not None:
            db.refresh(user_db)

    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e

    return user_db


def update_user_last_login_at(user_id: UUID, db: Session = Depends(get_session)):
    user_data = UserPatchModel(last_login_at=datetime.now(timezone.utc))  # type: ignore

    return update_user(user_id, user_data, db)
