from __future__ import annotations

import secrets
from datetime import datetime, timezone
from uuid import UUID

from passlib.context import CryptContext
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.initial_setup.setup import get_or_create_default_folder
from langflow.services.database.models.user.crud import get_user_by_username
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_variable_service

from .models import KeycloakGroupMapping

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def find_langflow_username(db: AsyncSession, groups: list[str]) -> str | None:
    """Return the shared Langflow username for the first matching Keycloak group.

    Groups are checked in order; the first match wins.
    Returns None if no mapping is found.
    """
    if not groups:
        return None

    stmt = select(KeycloakGroupMapping).where(KeycloakGroupMapping.keycloak_group.in_(groups))
    result = await db.exec(stmt)
    mappings = result.all()

    if not mappings:
        return None

    # Respect the order of groups as they appear in the token
    mapping_by_group = {m.keycloak_group: m.langflow_username for m in mappings}
    for group in groups:
        if group in mapping_by_group:
            return mapping_by_group[group]

    return None


async def get_or_create_shared_user(db: AsyncSession, username: str) -> User:
    """Return the shared Langflow user, creating it automatically if it doesn't exist."""
    user = await get_user_by_username(db, username)
    if user is not None:
        return user

    # Create the shared account with a random password (nobody logs in with it directly)
    random_password = secrets.token_urlsafe(32)
    hashed = _pwd_context.hash(random_password)

    user = User(
        username=username,
        password=hashed,
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    await db.flush()  # Populate user.id

    # Initialize default folder and variables (mirrors the login endpoint behaviour)
    await get_or_create_default_folder(db, user.id)
    await get_variable_service().initialize_user_variables(user.id, db)

    return user


async def list_mappings(db: AsyncSession) -> list[KeycloakGroupMapping]:
    result = await db.exec(select(KeycloakGroupMapping))
    return list(result.all())


async def create_mapping(db: AsyncSession, keycloak_group: str, langflow_username: str) -> KeycloakGroupMapping:
    mapping = KeycloakGroupMapping(
        keycloak_group=keycloak_group,
        langflow_username=langflow_username,
    )
    db.add(mapping)
    await db.flush()
    return mapping


async def delete_mapping(db: AsyncSession, mapping_id: UUID) -> bool:
    stmt = select(KeycloakGroupMapping).where(KeycloakGroupMapping.id == mapping_id)
    mapping = (await db.exec(stmt)).first()
    if mapping is None:
        return False
    await db.delete(mapping)
    await db.flush()
    return True


async def ensure_table(db: AsyncSession) -> None:
    """Create the mapping table if it does not yet exist (dev/simple deployments)."""
    from sqlalchemy import inspect
    from sqlmodel import SQLModel

    conn = await db.connection()

    def _has_table(sync_conn) -> bool:  # type: ignore[no-untyped-def]
        return inspect(sync_conn).has_table("keycloak_group_mapping")

    exists = await conn.run_sync(_has_table)
    if not exists:
        from .models import KeycloakGroupMapping  # noqa: F401 — registers the table in metadata

        def _create(sync_conn) -> None:  # type: ignore[no-untyped-def]
            SQLModel.metadata.create_all(sync_conn, tables=[KeycloakGroupMapping.__table__])

        await conn.run_sync(_create)
