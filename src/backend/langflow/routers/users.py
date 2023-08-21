from uuid import UUID
from langflow.services.database.models.user import (
    User,
    UserAddModel,
    UserListModel,
    UserPatchModel,
    UsersResponse,
)

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from sqlmodel import Session, select
from fastapi import APIRouter, Depends, HTTPException

from langflow.services.utils import get_session
from langflow.auth.auth import get_current_active_user, get_password_hash
from langflow.services.database.models.user import (
    update_user,
)

router = APIRouter(tags=["Login"])


@router.post("/user", response_model=UserListModel)
def add_user(
    user: UserAddModel,
    db: Session = Depends(get_session),
) -> User:
    """
    Add a new user to the database.
    """
    new_user = User(**user.dict())
    try:
        new_user.password = get_password_hash(user.password)

        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="User exists") from e

    return new_user


@router.get("/user", response_model=UserListModel)
def read_current_user(current_user: User = Depends(get_current_active_user)) -> User:
    """
    Retrieve the current user's data.
    """
    return current_user


@router.get("/users", response_model=UsersResponse)
def read_all_users(
    skip: int = 0,
    limit: int = 10,
    _: Session = Depends(get_current_active_user),
    db: Session = Depends(get_session),
) -> UsersResponse:
    """
    Retrieve a list of users from the database with pagination.
    """
    query = select(User).offset(skip).limit(limit)
    users = db.execute(query).fetchall()

    count_query = select(func.count()).select_from(User)  # type: ignore
    total_count = db.execute(count_query).scalar()

    return UsersResponse(
        total_count=total_count,  # type: ignore
        users=[UserListModel(**dict(user.User)) for user in users],
    )


@router.patch("/user/{user_id}", response_model=UserListModel)
def patch_user(
    user_id: UUID,
    user: UserPatchModel,
    _: Session = Depends(get_current_active_user),
    db: Session = Depends(get_session),
) -> User:
    """
    Update an existing user's data.
    """
    return update_user(user_id, user, db)


@router.delete("/user/{user_id}")
def delete_user(
    user_id: UUID,
    _: Session = Depends(get_current_active_user),
    db: Session = Depends(get_session),
) -> dict:
    """
    Delete a user from the database.
    """
    user_db = db.query(User).filter(User.id == user_id).first()
    if not user_db:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(user_db)
    db.commit()

    return {"detail": "User deleted"}


# TODO: REMOVE - Just for testing purposes
@router.post("/super_user", response_model=User)
def add_super_user_for_testing_purposes_delete_me_before_merge_into_dev(
    db: Session = Depends(get_session),
) -> User:
    """
    Add a superuser for testing purposes.
    (This should be removed in production)
    """
    new_user = User(
        username="superuser",
        password=get_password_hash("12345"),
        is_active=True,
        is_superuser=True,
        last_login_at=None,
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="User exists") from e

    return new_user
