from datetime import datetime, timezone
from typing import Optional, Union
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import Session, select

from langflow.services.database.models.user.model import User, UserUpdate
from langflow.services.deps import get_session


def get_user_by_username(db: Session, username: str) -> Union[User, None]:
    return db.exec(select(User).where(User.username == username)).first()


def get_user_by_id(db: Session, id: UUID) -> Union[User, None]:
    return db.exec(select(User).where(User.id == id)).first()


def update_user(user_db: Optional[User], user: UserUpdate, db: Session = Depends(get_session)) -> User:
    if not user_db:
        raise HTTPException(status_code=404, detail="User not found")

    # user_db_by_username = get_user_by_username(db, user.username)  # type: ignore
    # if user_db_by_username and user_db_by_username.id != user_id:
    #     raise HTTPException(status_code=409, detail="Username already exists")

    user_data = user.model_dump(exclude_unset=True)
    changed = False
    for attr, value in user_data.items():
        if hasattr(user_db, attr) and value is not None:
            setattr(user_db, attr, value)
            changed = True

    if not changed:
        raise HTTPException(status_code=status.HTTP_304_NOT_MODIFIED, detail="Nothing to update")

    user_db.updated_at = datetime.now(timezone.utc)
    flag_modified(user_db, "updated_at")

    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e

    return user_db


def update_user_last_login_at(user_id: UUID, db: Session = Depends(get_session)):
    try:
        user_data = UserUpdate(last_login_at=datetime.now(timezone.utc))  # type: ignore
        user = get_user_by_id(db, user_id)
        return update_user(user, user_data, db)
    except Exception:
        pass
