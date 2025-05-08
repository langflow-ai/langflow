from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from loguru import logger
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.database.models.user.model import User, UserUpdate


async def get_user_by_username(db: AsyncSession, username: str, include_deleted: bool = False) -> User | None:  # noqa: FBT001, FBT002
    """Get a user by username.

    Args:
        db: The database session
        username: The username to look up
        include_deleted: Whether to include soft-deleted users

    Returns:
        The user or None if not found
    """
    if include_deleted:
        stmt = select(User).where(User.username == username)
    else:
        stmt = select(User).where(User.username == username, User.is_deleted == False)  # noqa: E712
    return (await db.exec(stmt)).first()


async def get_user_by_id(db: AsyncSession, user_id: UUID, include_deleted: bool = False) -> User | None:  # noqa: FBT001, FBT002
    """Get a user by ID.

    Args:
        db: The database session
        user_id: The user ID to look up
        include_deleted: Whether to include soft-deleted users

    Returns:
        The user or None if not found
    """
    if isinstance(user_id, str):
        user_id = UUID(user_id)

    if include_deleted:
        stmt = select(User).where(User.id == user_id)
    else:
        stmt = select(User).where(User.id == user_id, User.is_deleted == False)  # noqa: E712
    return (await db.exec(stmt)).first()


async def soft_delete_user(db: AsyncSession, user: User) -> User:
    """Soft delete a user.

    Args:
        db: The database session
        user: The user to soft delete

    Returns:
        The updated user
    """
    user.is_deleted = True
    user.deleted_at = datetime.now(timezone.utc)
    update_data = UserUpdate(is_deleted=True, deleted_at=datetime.now(timezone.utc))
    return await update_user(user, update_data, db)


async def update_user(user_db: User | None, user: UserUpdate, db: AsyncSession) -> User:
    if not user_db:
        raise HTTPException(status_code=404, detail="User not found")

    # user_db_by_username = get_user_by_username(db, user.username)
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
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e

    return user_db


async def update_user_last_login_at(user_id: UUID, db: AsyncSession):
    try:
        user_data = UserUpdate(last_login_at=datetime.now(timezone.utc))
        user = await get_user_by_id(db, user_id)
        return await update_user(user, user_data, db)
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error updating user last login at: {e!s}")
