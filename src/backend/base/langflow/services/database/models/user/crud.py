from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from lfx.log.logger import logger
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.database.models.user.model import User, UserUpdate

USERNAME_UNAVAILABLE = "This username is unavailable."


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    stmt = select(User).where(User.username == username)
    return (await db.exec(stmt)).first()


async def get_user_by_username_case_insensitive(db: AsyncSession, username: str) -> User | None:
    """Return the user whose username collides with ``username`` under ``ix_user_username_lower``.

    Use this, not ``get_user_by_username``, to decide whether a username is free
    to create: an exact-match miss can still violate the case-insensitive unique
    index. Both sides are lowered in the database so the comparison uses the
    index's own ``lower()`` (ASCII-only on SQLite, locale-aware on Postgres).
    """
    stmt = select(User).where(func.lower(User.username) == func.lower(username))
    return (await db.exec(stmt)).first()


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> User | None:
    if isinstance(user_id, str):
        user_id = UUID(user_id)
    stmt = select(User).where(User.id == user_id)
    return (await db.exec(stmt)).first()


async def update_user(user_db: User | None, user: UserUpdate, db: AsyncSession) -> User:
    if not user_db:
        raise HTTPException(status_code=404, detail="User not found")

    # Check before mutating: a failed flush poisons the request session, so the
    # IntegrityError below would surface as a 500 from the caller's error path.
    if user.username is not None and user.username != user_db.username:
        existing = await get_user_by_username_case_insensitive(db, user.username)
        if existing is not None and existing.id != user_db.id:
            raise HTTPException(status_code=400, detail=USERNAME_UNAVAILABLE)

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
        await db.flush()
    except IntegrityError as e:
        # Concurrent-rename race past the check above. The only unique constraints a
        # user update can hit are on ``username``; don't echo the raw SQL back.
        raise HTTPException(status_code=400, detail=USERNAME_UNAVAILABLE) from e

    return user_db


async def update_user_last_login_at(user_id: UUID, db: AsyncSession):
    try:
        user_data = UserUpdate(last_login_at=datetime.now(timezone.utc))
        user = await get_user_by_id(db, user_id)
        return await update_user(user, user_data, db)
    except Exception as e:  # noqa: BLE001
        await logger.aerror(f"Error updating user last login at: {e!s}")


async def get_all_superusers(db: AsyncSession) -> list[User]:
    """Get all superuser accounts from the database."""
    stmt = select(User).where(User.is_superuser == True)  # noqa: E712
    result = await db.exec(stmt)
    return list(result.all())
