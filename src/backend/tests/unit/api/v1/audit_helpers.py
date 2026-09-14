"""Shared helpers for the audit producer tests: read events back from the real database."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from langflow.services.database.models.audit_event.model import AuditEvent
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_auth_service, get_settings_service, session_scope
from sqlmodel import col, select

if TYPE_CHECKING:
    from collections.abc import Iterator

PASSWORD = "audit-test-password"  # noqa: S105  # pragma: allowlist secret


def enabled_audit() -> Iterator[None]:
    settings = get_settings_service().settings
    original = settings.audit_enabled
    settings.audit_enabled = True
    try:
        yield
    finally:
        settings.audit_enabled = original


async def events_for(resource_id: UUID | str, *, resource_type: str | None = None) -> list[AuditEvent]:
    async with session_scope() as session:
        statement = select(AuditEvent).where(AuditEvent.resource_id == UUID(str(resource_id)))
        if resource_type is not None:
            statement = statement.where(AuditEvent.resource_type == resource_type)
        statement = statement.order_by(col(AuditEvent.timestamp), col(AuditEvent.id))
        return list((await session.exec(statement)).all())


async def events_by_user(user_id: UUID) -> list[AuditEvent]:
    async with session_scope() as session:
        statement = select(AuditEvent).where(AuditEvent.user_id == user_id)
        statement = statement.order_by(col(AuditEvent.timestamp), col(AuditEvent.id))
        return list((await session.exec(statement)).all())


async def make_user(prefix: str) -> tuple[UUID, str]:
    username = f"{prefix}_{uuid4().hex}"
    async with session_scope() as session:
        user = User(username=username, password=get_auth_service().get_password_hash(PASSWORD), is_active=True)
        session.add(user)
        await session.flush()
        user_id = user.id
    return user_id, username


async def login(client, username: str) -> dict[str, str]:
    response = await client.post("api/v1/login", data={"username": username, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
