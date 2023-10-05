from uuid import UUID
from langflow.api.v1.schemas import UsersResponse
from langflow.services.database.models.user import (
    User,
    UserCreate,
    UserRead,
    UserUpdate,
)

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from sqlmodel import Session, select
from fastapi import APIRouter, Depends, HTTPException

from langflow.services.getters import get_session, get_settings_service
from langflow.services.auth.utils import (
    get_current_active_superuser,
    get_current_active_user,
    get_password_hash,
    verify_password,
)
from langflow.services.database.models.user.crud import (
    get_user_by_id,
    update_user,
)

router = APIRouter(tags=["Users"], prefix="/users")


@router.post("/", response_model=UserRead, status_code=201)
def add_user(
    user: UserCreate,
    session: Session = Depends(get_session),
    settings_service=Depends(get_settings_service),
) -> User:
    """
    Add a new user to the database.
    """
    new_user = User.from_orm(user)
    try:
        new_user.password = get_password_hash(user.password)
        new_user.is_active = settings_service.auth_settings.NEW_USER_IS_ACTIVE
        session.add(new_user)
        session.commit()
        session.refresh(new_user)
    except IntegrityError as e:
        session.rollback()
        raise HTTPException(
            status_code=400, detail="This username is unavailable."
        ) from e

    return new_user


@router.get("/whoami", response_model=UserRead)
def read_current_user(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """
    Retrieve the current user's data.
    """
    return current_user


@router.get("/", response_model=UsersResponse)
def read_all_users(
    skip: int = 0,
    limit: int = 10,
    _: Session = Depends(get_current_active_superuser),
    session: Session = Depends(get_session),
) -> UsersResponse:
    """
    Retrieve a list of users from the database with pagination.
    """
    query = select(User).offset(skip).limit(limit)
    users = session.execute(query).fetchall()

    count_query = select(func.count()).select_from(User)  # type: ignore
    total_count = session.execute(count_query).scalar()

    return UsersResponse(
        total_count=total_count,  # type: ignore
        users=[UserRead(**dict(user.User)) for user in users],
    )


@router.patch("/{user_id}", response_model=UserRead)
def patch_user(
    user_id: UUID,
    user_update: UserUpdate,
    user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
) -> User:
    """
    Update an existing user's data.
    """
    if not user.is_superuser and user.id != user_id:
        raise HTTPException(
            status_code=403, detail="You don't have the permission to update this user"
        )
    if user_update.password:
        if not user.is_superuser:
            raise HTTPException(
                status_code=400, detail="You can't change your password here"
            )
        user_update.password = get_password_hash(user_update.password)

    if user_db := get_user_by_id(session, user_id):
        return update_user(user_db, user_update, session)
    else:
        raise HTTPException(status_code=404, detail="User not found")


@router.patch("/{user_id}/reset-password", response_model=UserRead)
def reset_password(
    user_id: UUID,
    user_update: UserUpdate,
    user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
) -> User:
    """
    Reset a user's password.
    """
    if user_id != user.id:
        raise HTTPException(
            status_code=400, detail="You can't change another user's password"
        )

    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if verify_password(user_update.password, user.password):
        raise HTTPException(
            status_code=400, detail="You can't use your current password"
        )
    new_password = get_password_hash(user_update.password)
    user.password = new_password
    session.commit()
    session.refresh(user)

    return user


@router.delete("/{user_id}", response_model=dict)
def delete_user(
    user_id: UUID,
    current_user: User = Depends(get_current_active_superuser),
    session: Session = Depends(get_session),
) -> dict:
    """
    Delete a user from the database.
    """
    if current_user.id == user_id:
        raise HTTPException(
            status_code=400, detail="You can't delete your own user account"
        )
    elif not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="You don't have the permission to delete this user"
        )

    user_db = session.query(User).filter(User.id == user_id).first()
    if not user_db:
        raise HTTPException(status_code=404, detail="User not found")

    session.delete(user_db)
    session.commit()

    return {"detail": "User deleted"}
