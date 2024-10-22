from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.sql.expression import SelectOfScalar

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.v1.schemas import UsersResponse
from langflow.services.auth.utils import (
    get_current_active_superuser,
    get_password_hash,
    verify_password,
)
from langflow.services.database.models.folder.utils import create_default_folder_if_it_doesnt_exist
from langflow.services.database.models.user import User, UserCreate, UserRead, UserUpdate
from langflow.services.database.models.user.crud import get_user_by_id, update_user
from langflow.services.deps import get_settings_service

router = APIRouter(tags=["Users"], prefix="/users")


@router.post("/", response_model=UserRead, status_code=201)
def add_user(
    user: UserCreate,
    session: DbSession,
) -> User:
    """Add a new user to the database."""
    new_user = User.model_validate(user, from_attributes=True)
    try:
        new_user.password = get_password_hash(user.password)
        new_user.is_active = get_settings_service().auth_settings.NEW_USER_IS_ACTIVE
        session.add(new_user)
        session.commit()
        session.refresh(new_user)
        folder = create_default_folder_if_it_doesnt_exist(session, new_user.id)
        if not folder:
            raise HTTPException(status_code=500, detail="Error creating default folder")
    except IntegrityError as e:
        session.rollback()
        raise HTTPException(status_code=400, detail="This username is unavailable.") from e

    return new_user


@router.get("/whoami", response_model=UserRead)
def read_current_user(
    current_user: CurrentActiveUser,
) -> User:
    """Retrieve the current user's data."""
    return current_user


@router.get("/", dependencies=[Depends(get_current_active_superuser)])
def read_all_users(
    *,
    skip: int = 0,
    limit: int = 10,
    session: DbSession,
) -> UsersResponse:
    """Retrieve a list of users from the database with pagination."""
    query: SelectOfScalar = select(User).offset(skip).limit(limit)
    users = session.exec(query).fetchall()

    count_query = select(func.count()).select_from(User)
    total_count = session.exec(count_query).first()

    return UsersResponse(
        total_count=total_count,
        users=[UserRead(**user.model_dump()) for user in users],
    )


@router.patch("/{user_id}", response_model=UserRead)
def patch_user(
    user_id: UUID,
    user_update: UserUpdate,
    user: CurrentActiveUser,
    session: DbSession,
) -> User:
    """Update an existing user's data."""
    update_password = bool(user_update.password)

    if not user.is_superuser and user_update.is_superuser:
        raise HTTPException(status_code=403, detail="Permission denied")

    if not user.is_superuser and user.id != user_id:
        raise HTTPException(status_code=403, detail="Permission denied")
    if update_password:
        if not user.is_superuser:
            raise HTTPException(status_code=400, detail="You can't change your password here")
        user_update.password = get_password_hash(user_update.password)

    if user_db := get_user_by_id(session, user_id):
        if not update_password:
            user_update.password = user_db.password
        return update_user(user_db, user_update, session)
    raise HTTPException(status_code=404, detail="User not found")


@router.patch("/{user_id}/reset-password", response_model=UserRead)
def reset_password(
    user_id: UUID,
    user_update: UserUpdate,
    user: CurrentActiveUser,
    session: DbSession,
) -> User:
    """Reset a user's password."""
    if user_id != user.id:
        raise HTTPException(status_code=400, detail="You can't change another user's password")

    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if verify_password(user_update.password, user.password):
        raise HTTPException(status_code=400, detail="You can't use your current password")
    new_password = get_password_hash(user_update.password)
    user.password = new_password
    session.commit()
    session.refresh(user)

    return user


@router.delete("/{user_id}")
def delete_user(
    user_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_superuser)],
    session: DbSession,
) -> dict:
    """Delete a user from the database."""
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="You can't delete your own user account")
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Permission denied")

    user_db = session.exec(select(User).where(User.id == user_id)).first()
    if not user_db:
        raise HTTPException(status_code=404, detail="User not found")

    session.delete(user_db)
    session.commit()

    return {"detail": "User deleted"}
