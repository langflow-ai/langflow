"""Tests for the authz_audit_log retention helper and pass-through startup warning."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langflow.services.authorization.service import LangflowAuthorizationService
from langflow.services.database.models.auth import AuthzAuditLog
from langflow.services.utils import clean_authz_audit_log
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession


@pytest.fixture(name="authz_engine")
def authz_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    yield engine
    engine.sync_engine.dispose()


@pytest.fixture(name="authz_session")
async def authz_session(authz_engine):
    async with authz_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(authz_engine, expire_on_commit=False) as session:
        yield session
    async with authz_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await authz_engine.dispose()


def _audit_row(*, days_old: int) -> AuthzAuditLog:
    timestamp = datetime.now(timezone.utc) - timedelta(days=days_old)
    return AuthzAuditLog(
        user_id=uuid4(),
        action="flow:read",
        resource_type="flow",
        resource_id=uuid4(),
        result="allow",
        details={"domain": "*"},
        timestamp=timestamp,
    )


def _settings(*, retention_days: int) -> SimpleNamespace:
    return SimpleNamespace(
        auth_settings=SimpleNamespace(
            AUTHZ_AUDIT_RETENTION_DAYS=retention_days,
        ),
    )


@pytest.mark.anyio
async def test_clean_authz_audit_log_prunes_rows_past_retention(authz_session):
    """Rows older than the retention window are deleted; fresh rows survive."""
    authz_session.add(_audit_row(days_old=120))  # outside 90-day window
    authz_session.add(_audit_row(days_old=95))  # outside 90-day window
    authz_session.add(_audit_row(days_old=5))  # inside window
    await authz_session.commit()

    await clean_authz_audit_log(_settings(retention_days=90), authz_session)
    await authz_session.commit()

    surviving = (await authz_session.exec(select(AuthzAuditLog))).all()
    # Only the 5-day-old row should remain.
    assert len(surviving) == 1


@pytest.mark.anyio
async def test_clean_authz_audit_log_zero_disables_retention(authz_session):
    """A retention of 0 days is a no-op so external archival pipelines can manage the table."""
    for days_old in (1, 30, 200, 365):
        authz_session.add(_audit_row(days_old=days_old))
    await authz_session.commit()

    await clean_authz_audit_log(_settings(retention_days=0), authz_session)
    await authz_session.commit()

    surviving = (await authz_session.exec(select(AuthzAuditLog))).all()
    assert len(surviving) == 4


@pytest.mark.anyio
async def test_clean_authz_audit_log_empty_table(authz_session):
    """Pruning an empty table is a no-op and must not raise."""
    deleted = await clean_authz_audit_log(_settings(retention_days=30), authz_session)
    assert deleted in (0, -1)  # -1 acceptable when driver doesn't report rowcount


class _RecordingLogger:
    """Stand-in for loguru's logger that records each call by level."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def warning(self, message: str, *args, **kwargs) -> None:  # noqa: ARG002
        self.calls.append(("warning", message))

    def debug(self, message: str, *args, **kwargs) -> None:  # noqa: ARG002
        self.calls.append(("debug", message))

    def info(self, message: str, *args, **kwargs) -> None:  # noqa: ARG002
        self.calls.append(("info", message))


@pytest.mark.anyio
async def test_passthrough_warning_emitted_when_authz_enabled(monkeypatch):
    """LangflowAuthorizationService warns when AUTHZ_ENABLED=True but plugin is missing."""
    from langflow.services.authorization import service as authz_service_module

    recorder = _RecordingLogger()
    monkeypatch.setattr(authz_service_module, "logger", recorder)

    settings = SimpleNamespace(
        auth_settings=SimpleNamespace(
            AUTHZ_ENABLED=True,
            AUTHZ_SUPERUSER_BYPASS=True,
        )
    )
    LangflowAuthorizationService(settings)

    warning_messages = [msg for level, msg in recorder.calls if level == "warning"]
    assert any("OSS pass-through" in msg for msg in warning_messages), (
        f"Expected a WARNING about the OSS pass-through service; got {warning_messages}"
    )


@pytest.mark.anyio
async def test_passthrough_warning_silent_when_authz_disabled(monkeypatch):
    """No warning is emitted when AUTHZ_ENABLED=False."""
    from langflow.services.authorization import service as authz_service_module

    recorder = _RecordingLogger()
    monkeypatch.setattr(authz_service_module, "logger", recorder)

    settings = SimpleNamespace(
        auth_settings=SimpleNamespace(
            AUTHZ_ENABLED=False,
            AUTHZ_SUPERUSER_BYPASS=True,
        )
    )
    LangflowAuthorizationService(settings)

    warning_messages = [msg for level, msg in recorder.calls if level == "warning"]
    assert not any("OSS pass-through" in msg for msg in warning_messages), (
        f"No pass-through warning expected when AUTHZ_ENABLED=False; got {warning_messages}"
    )
