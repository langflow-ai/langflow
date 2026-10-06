"""Shared helpers for the audit producer tests: read events back from the real database."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from langflow.services.authorization.audit import get_audit_producer_health
from langflow.services.database.models.audit_event.model import AuditEvent
from langflow.services.database.models.auth.authz import AuthzAuditLog
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


async def make_user(prefix: str, *, superuser: bool = False) -> tuple[UUID, str]:
    username = f"{prefix}_{uuid4().hex}"
    async with session_scope() as session:
        user = User(
            username=username,
            password=get_auth_service().get_password_hash(PASSWORD),
            is_active=True,
            is_superuser=superuser,
        )
        session.add(user)
        await session.flush()
        user_id = user.id
    return user_id, username


async def record_event(**fields) -> AuditEvent:
    """Insert one event straight into the table.

    What a caller other than the owner produces in a deployment that has an
    authorization plugin. Without one the API refuses them a resource they do
    not own, so the row cannot be made through a route.
    """
    defaults = {
        "event_type": "action",
        "result": "succeeded",
        "actor_type": "user",
        "request_id": uuid4(),
        "details": {"schema_version": 1},
    }
    event = AuditEvent(**{**defaults, **fields})
    async with session_scope() as session:
        session.add(event)
        await session.flush()
        await session.refresh(event)
        session.expunge(event)
    return event


async def login(client, username: str) -> dict[str, str]:
    response = await client.post("api/v1/login", data={"username": username, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def authz_rows_for(user_id: UUID) -> int:
    """Count the authorization decisions stored for *user_id*, once the writer is idle.

    An empty queue is not enough: the writer may hold a batch it has not
    committed yet, so wait until every submitted row is persisted or failed.
    """
    for _ in range(250):
        health = get_audit_producer_health()
        settled = int(health.get("persisted_count") or 0) + int(health.get("failed_count") or 0)
        if health.get("queue_depth", 0) == 0 and settled >= int(health.get("submitted_count") or 0):
            break
        await asyncio.sleep(0.02)
    async with session_scope() as session:
        rows = (await session.exec(select(AuthzAuditLog).where(AuthzAuditLog.user_id == user_id))).all()
        return len(rows)
