from datetime import datetime, timezone
from typing import Union
from uuid import UUID
from fastapi import Depends, HTTPException, status
from langflow.services.database.models.user.user import User, UserUpdate
from langflow.services.getters import get_session
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session
from typing import Optional

from sqlalchemy.orm.attributes import flag_modified


def get_user_by_username(db: Session, username: str) -> Union[User, None]:
    return db.query(User).filter(User.username == username).first()


def get_user_by_id(db: Session, id: UUID) -> Union[User, None]:
    return db.query(User).filter(User.id == id).first()


def update_user(
    user_db: Optional[User], user: UserUpdate, db: Session = Depends(get_session)
) -> User:
    if not user_db:
        raise HTTPException(status_code=404, detail="User not found")

    # user_db_by_username = get_user_by_username(db, user.username)  # type: ignore
    # if user_db_by_username and user_db_by_username.id != user_id:
    #     raise HTTPException(status_code=409, detail="Username already exists")

    user_data = user.dict(exclude_unset=True)
    changed = False
    for attr, value in user_data.items():
        if hasattr(user_db, attr) and value is not None:
            setattr(user_db, attr, value)
            changed = True

    if not changed:
        raise HTTPException(
            status_code=status.HTTP_304_NOT_MODIFIED, detail="Nothing to update"
        )

    user_db.updated_at = datetime.now(timezone.utc)
    flag_modified(user_db, "updated_at")

    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e

    return user_db


def update_user_last_login_at(user_id: UUID, db: Session = Depends(get_session)):
    user_data = UserUpdate(last_login_at=datetime.now(timezone.utc))  # type: ignore
    user = get_user_by_id(db, user_id)
    return update_user(user, user_data, db)
