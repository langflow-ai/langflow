from uuid import UUID
from sqlmodel import Session, select
from datetime import timezone, datetime
from sqlalchemy.exc import IntegrityError
from fastapi import APIRouter, Depends, HTTPException

from langflow.services.utils import get_session
from langflow.auth.auth import get_current_active_user, get_password_hash
from langflow.database.models.user import (
    User,
    UserAddModel,
    UserListModel,
    UserPatchModel,
    get_user_by_id,
    get_user_by_username,
)

router = APIRouter(tags=["Login"])


@router.get("/user", response_model=UserListModel)
def read_current_user(current_user: User = Depends(get_current_active_user)):
    return current_user


@router.get("/users")
def read_all_users(
    skip: int = 0,
    limit: int = 10,
    _: Session = Depends(get_current_active_user),
    db: Session = Depends(get_session),
):
    query = select(User)
    query = query.offset(skip).limit(limit)

    return db.execute(query).fetchall()


@router.post("/user", response_model=UserListModel)
def add_user(
    user: UserAddModel,
    _: Session = Depends(get_current_active_user),
    db: Session = Depends(get_session),
):
    new_user = User(**user.dict())
    try:
        new_user.password = get_password_hash(user.password)

        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except IntegrityError as e:
        db.rollback()

        raise HTTPException(
            status_code=400,
            detail="User exists",
        ) from e

    return new_user


@router.patch("/user/{user_id}", response_model=UserListModel)
def update_user(
    user_id: UUID,
    user: UserPatchModel,
    _: Session = Depends(get_current_active_user),
    db: Session = Depends(get_session),
):
    user_db = get_user_by_username(db, user.username)
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

        raise HTTPException(
            status_code=400,
            detail=str(e),
        ) from e

    return user_db


@router.delete("/user/{user_id}")
def delete_user(
    user_id: UUID,
    _: Session = Depends(get_current_active_user),
    db: Session = Depends(get_session),
):
    user_db = db.query(User).filter(User.id == user_id).first()
    if not user_db:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(user_db)
    db.commit()

    return {"detail": "User deleted"}


# TODO: REMOVE - Just for testing purposes
@router.post("/super_user", response_model=User)
def add_super_user_to_testing_purposes(db: Session = Depends(get_session)):
    new_user = User(username="superuser", password="12345", is_superuser=True)

    try:
        new_user.password = get_password_hash(new_user.password)

        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="User exists",
        ) from e

    return new_user
