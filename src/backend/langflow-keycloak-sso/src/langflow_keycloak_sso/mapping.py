from __future__ import annotations

import secrets

from langflow.initial_setup.setup import get_or_create_default_folder
from langflow.services.database.models.user.crud import get_user_by_username
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_variable_service
from passlib.context import CryptContext
from sqlmodel.ext.asyncio.session import AsyncSession

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def get_or_create_shared_user(db: AsyncSession, username: str) -> User:
    """Return the shared Langflow user, creating it automatically if it doesn't exist.

    The account is created with a random password so it cannot be used for
    direct username/password login — only SSO via Keycloak is the entry point.
    """
    user = await get_user_by_username(db, username)
    if user is not None:
        return user

    hashed = _pwd_context.hash(secrets.token_urlsafe(32))
    user = User(
        username=username,
        password=hashed,
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    await db.flush()

    await get_or_create_default_folder(db, user.id)
    await get_variable_service().initialize_user_variables(user.id, db)

    return user
