from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from langflow.services.audit.attribution import AuditActor
from langflow.services.audit.vocabulary import (
    PROJECT_WRITE,
    AuditActorType,
    AuditEventType,
    AuditOperation,
    AuditResourceType,
    AuditResult,
)
from langflow.services.audit.writer import AuditEventDraft
from langflow.services.database.models.audit_event.model import AuditEvent
from langflow.services.deps import get_settings_service
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Iterator


@pytest.fixture
async def audit_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(AuditEvent.metadata.create_all, tables=[AuditEvent.__table__])
    yield engine
    await engine.dispose()


@pytest.fixture
async def audit_session(audit_engine) -> AsyncIterator[AsyncSession]:
    async with AsyncSession(audit_engine, expire_on_commit=False) as session:
        yield session


@pytest.fixture
def audit_enabled() -> Iterator[None]:
    settings = get_settings_service().settings
    original = settings.audit_enabled
    settings.audit_enabled = True
    yield
    settings.audit_enabled = original


@pytest.fixture
def audit_disabled() -> Iterator[None]:
    settings = get_settings_service().settings
    original = settings.audit_enabled
    settings.audit_enabled = False
    yield
    settings.audit_enabled = original


@pytest.fixture
def excluded_events() -> Iterator[Callable[[str], None]]:
    """Set LANGFLOW_AUDIT_EXCLUDE_EVENTS for one test, as the env var would."""
    settings = get_settings_service().settings
    original = list(settings.audit_exclude_events)

    def apply(value: str) -> None:
        settings.audit_exclude_events = value

    yield apply
    settings.audit_exclude_events = original


def user_actor(user_id: UUID | None = None) -> AuditActor:
    resolved = user_id or uuid4()
    return AuditActor(user_id=resolved, actor_type=AuditActorType.USER, actor_id=resolved)


def project_patch_draft(**overrides) -> AuditEventDraft:
    values = {
        "resource_type": AuditResourceType.PROJECT,
        "resource_id": uuid4(),
        "resource_name": "support-automation",
        "action": PROJECT_WRITE,
        "operation": AuditOperation.PATCH,
        "event_type": AuditEventType.ACTION,
        "result": AuditResult.SUCCEEDED,
        "actor": user_actor(),
        "details": {"schema_version": 1, "description": "Routes customer questions"},
    }
    values.update(overrides)
    return AuditEventDraft(**values)
