from datetime import datetime, timezone
from uuid import UUID
from fastapi import Depends, HTTPException
from langflow.services.database.models.user.user import User, UserUpdate
from langflow.services.utils import get_session
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def get_user_by_username(db: Session, username: str) -> User:
    db_user = db.query(User).filter(User.username == username).first()
    return User.from_orm(db_user) if db_user else None  # type: ignore


def get_user_by_id(db: Session, id: UUID) -> User:
    db_user = db.query(User).filter(User.id == id).first()
    return User.from_orm(db_user) if db_user else None  # type: ignore


def update_user(
    user_id: UUID, user: UserUpdate, db: Session = Depends(get_session)
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
    user_data = UserUpdate(last_login_at=datetime.now(timezone.utc))  # type: ignore

    return update_user(user_id, user_data, db)
