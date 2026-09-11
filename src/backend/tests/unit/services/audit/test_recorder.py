"""The recorder's two promises: it never costs the write, and it needs no database.

Exercised against a real session rather than a stand-in. The seam opens a
savepoint and flushes, so a fake that only implements ``add`` would prove
nothing about the behaviour that matters.
"""

import pytest
import sqlalchemy as sa
from langflow.services.audit.events import FLOW_UPDATED
from langflow.services.audit.recorder import ALLOWED_PAYLOAD_KEYS, record_audit_event
from langflow.services.database.models.audit_log.model import AuditLog
from langflow.services.deps import get_settings_service
from lfx.services.session import NoopSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(AuditLog.metadata.create_all, tables=[AuditLog.__table__])
    async with AsyncSession(engine) as s:
        yield s
    await engine.dispose()


async def rows(session: AsyncSession) -> list[AuditLog]:
    return list((await session.exec(select(AuditLog))).all())


@pytest.fixture
def audit_on():
    settings = get_settings_service().settings
    original = settings.audit_enabled, settings.audit_anonymize_payload
    settings.audit_enabled, settings.audit_anonymize_payload = True, False
    yield
    settings.audit_enabled, settings.audit_anonymize_payload = original


@pytest.fixture
def audit_off():
    settings = get_settings_service().settings
    original = settings.audit_enabled
    settings.audit_enabled = False
    yield
    settings.audit_enabled = original


@pytest.fixture
def anonymized():
    settings = get_settings_service().settings
    original = settings.audit_enabled, settings.audit_anonymize_payload
    settings.audit_enabled, settings.audit_anonymize_payload = True, True
    yield
    settings.audit_enabled, settings.audit_anonymize_payload = original


async def test_nothing_is_written_when_the_feature_is_off(session, audit_off):  # noqa: ARG001
    await record_audit_event(session, event=FLOW_UPDATED)

    assert await rows(session) == []


async def test_a_stateless_runtime_records_nothing_and_does_not_raise(audit_on):  # noqa: ARG001
    """``lfx serve`` has no database. The no-op must be deliberate, not incidental."""
    await record_audit_event(NoopSession(), event=FLOW_UPDATED)


async def test_a_recorded_row_carries_the_resource_taken_from_the_event_name(session, audit_on):  # noqa: ARG001
    await record_audit_event(session, event=FLOW_UPDATED)

    written = await rows(session)
    assert len(written) == 1
    assert written[0].resource_type == "flow"
    assert written[0].created_at is not None


async def test_a_key_outside_the_allowlist_never_reaches_the_row(session, audit_on):  # noqa: ARG001
    """The seam is the last line of defence: a careless producer must not leak."""
    await record_audit_event(
        session,
        event=FLOW_UPDATED,
        payload={"changes": ["Agent.api_key"], "api_key": "sk-leaked", "graph": {"nodes": []}},
    )

    payload = (await rows(session))[0].payload
    assert payload == {"changes": ["Agent.api_key"]}
    assert "sk-leaked" not in str(payload)
    assert set(payload) <= ALLOWED_PAYLOAD_KEYS


async def test_an_empty_payload_is_stored_as_null_rather_than_an_empty_object(session, audit_on):  # noqa: ARG001
    await record_audit_event(session, event=FLOW_UPDATED, payload={"reason": None})

    assert (await rows(session))[0].payload is None


async def test_anonymizing_drops_the_payload_but_keeps_the_row(session, anonymized):  # noqa: ARG001
    await record_audit_event(session, event=FLOW_UPDATED, payload={"changes": ["Agent.model_name"]})

    written = await rows(session)
    assert len(written) == 1
    assert written[0].payload is None


async def test_a_broken_event_name_is_dropped_rather_than_raised(session, audit_on):  # noqa: ARG001
    """Losing the description of a write must never lose the write."""
    await record_audit_event(session, event="not-an-audit-event")

    assert await rows(session) == []


async def test_a_payload_json_cannot_encode_never_reaches_the_database(session, audit_on):  # noqa: ARG001
    """A JSON column is encoded at flush, so a bad value would fail the caller's commit."""
    await record_audit_event(session, event=FLOW_UPDATED, payload={"changes": {object()}, "changes_total": 3})

    written = await rows(session)
    assert written[0].payload == {"changes_total": 3}, "the unencodable value is dropped, the count survives"
    await session.flush()  # the caller's own flush must still succeed


async def test_a_rejected_row_does_not_take_the_callers_write_with_it(session, audit_on):  # noqa: ARG001
    """The savepoint is the guarantee: the caller's transaction survives a bad row."""
    marker = sa.text("create table caller_work (id integer primary key)")
    await session.exec(marker)

    await record_audit_event(session, event=FLOW_UPDATED, payload={"changes": {object()}})
    await session.exec(sa.text("insert into caller_work (id) values (1)"))
    await session.flush()

    survived = (await session.exec(sa.text("select count(*) from caller_work"))).scalar_one()
    assert survived == 1, "the caller's work is committed even though the audit payload was bad"
