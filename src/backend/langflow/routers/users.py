from typing import List
from sqlmodel import Session, select
from sqlalchemy.exc import IntegrityError
from fastapi import APIRouter, Depends, HTTPException

from langflow.database.base import get_session
from langflow.auth.auth import get_current_active_user
from langflow.database.models.user import UserAddModel, UserListModel, User

from passlib.context import CryptContext

router = APIRouter(prefix="/users", tags=["Users"])


def get_password_hash(password):
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return pwd_context.hash(password)


@router.get("/user", response_model=UserListModel)
async def read_current_user(current_user: User = Depends(get_current_active_user)):
    return current_user


@router.get("/users", response_model=List[UserListModel])
async def read_all_users(
    skip: int = 0,
    limit: int = 10,
    _: Session = Depends(get_current_active_user),
    db: Session = Depends(get_session),
):
    query = select(User)
    query = query.offset(skip).limit(limit)

    return db.execute(query).fetchall()


@router.post("/user", response_model=User)
async def add_user(
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


# TODO: Remove - Just for testing purposes
@router.post("/super_user", response_model=User)
async def add_super_user_to_testing_purposes(db: Session = Depends(get_session)):
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
