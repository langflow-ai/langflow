"""The recorder's two promises: it never costs the write, and it needs no database.

Exercised against a real session rather than a stand-in: what matters here is
when the row reaches the database relative to the caller's own write, which a
fake that only implements ``add`` could not show.
"""

import pytest
import sqlalchemy as sa
from langflow.services.audit.events import FLOW_UPDATE
from langflow.services.audit.recorder import ALLOWED_PAYLOAD_KEYS, record_audit_event
from langflow.services.database.models.audit_event.model import AuditEvent, AuditFamily, AuditResult
from langflow.services.deps import get_settings_service
from lfx.services.session import NoopSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(AuditEvent.metadata.create_all, tables=[AuditEvent.__table__])
    async with AsyncSession(engine) as s:
        yield s
    await engine.dispose()


async def rows(session: AsyncSession) -> list[AuditEvent]:
    return list((await session.exec(select(AuditEvent))).all())


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
    await record_audit_event(session, event=FLOW_UPDATE, family=AuditFamily.ACTION, result=AuditResult.SUCCEEDED)

    assert await rows(session) == []


async def test_a_stateless_runtime_records_nothing_and_does_not_raise(audit_on):  # noqa: ARG001
    """``lfx serve`` has no database. The no-op must be deliberate, not incidental."""
    await record_audit_event(NoopSession(), event=FLOW_UPDATE, family=AuditFamily.ACTION, result=AuditResult.SUCCEEDED)


async def test_a_recorded_row_carries_the_resource_taken_from_the_event_name(session, audit_on):  # noqa: ARG001
    await record_audit_event(session, event=FLOW_UPDATE, family=AuditFamily.ACTION, result=AuditResult.SUCCEEDED)

    written = await rows(session)
    assert len(written) == 1
    assert written[0].resource_type == "flow"
    assert written[0].created_at is not None


async def test_a_key_outside_the_allowlist_never_reaches_the_row(session, audit_on):  # noqa: ARG001
    """The seam is the last line of defence: a careless producer must not leak."""
    await record_audit_event(
        session,
        event=FLOW_UPDATE,
        family=AuditFamily.ACTION,
        result=AuditResult.SUCCEEDED,
        payload={"changes": ["Agent.api_key"], "api_key": "sk-leaked", "graph": {"nodes": []}},
    )

    payload = (await rows(session))[0].payload
    assert payload == {"changes": ["Agent.api_key"]}
    assert "sk-leaked" not in str(payload)
    assert set(payload) <= ALLOWED_PAYLOAD_KEYS


async def test_an_empty_payload_is_stored_as_null_rather_than_an_empty_object(session, audit_on):  # noqa: ARG001
    await record_audit_event(
        session, event=FLOW_UPDATE, family=AuditFamily.ACTION, result=AuditResult.SUCCEEDED, payload={"reason": None}
    )

    assert (await rows(session))[0].payload is None


async def test_anonymizing_drops_the_payload_but_keeps_the_row(session, anonymized):  # noqa: ARG001
    await record_audit_event(
        session,
        event=FLOW_UPDATE,
        family=AuditFamily.ACTION,
        result=AuditResult.SUCCEEDED,
        payload={"changes": ["Agent.model_name"]},
    )

    written = await rows(session)
    assert len(written) == 1
    assert written[0].payload is None


async def test_a_broken_event_name_is_dropped_rather_than_raised(session, audit_on):  # noqa: ARG001
    """Losing the description of a write must never lose the write."""
    await record_audit_event(
        session,
        event="not-an-audit-event",
        family=AuditFamily.ACTION,
        result=AuditResult.SUCCEEDED,
    )

    assert await rows(session) == []


async def test_a_payload_json_cannot_encode_never_reaches_the_database(session, audit_on):  # noqa: ARG001
    """A JSON column is encoded at flush, so a bad value would fail the caller's commit."""
    await record_audit_event(
        session,
        event=FLOW_UPDATE,
        family=AuditFamily.ACTION,
        result=AuditResult.SUCCEEDED,
        payload={"changes": {object()}, "changes_total": 3},
    )

    written = await rows(session)
    assert written[0].payload == {"changes_total": 3}, "the unencodable value is dropped, the count survives"
    await session.flush()  # the caller's own flush must still succeed


async def test_a_rejected_row_does_not_take_the_callers_write_with_it(session, audit_on):  # noqa: ARG001
    """A bad payload is scrubbed before it is staged, so the caller's write stands."""
    marker = sa.text("create table caller_work (id integer primary key)")
    await session.exec(marker)

    await record_audit_event(
        session,
        event=FLOW_UPDATE,
        family=AuditFamily.ACTION,
        result=AuditResult.SUCCEEDED,
        payload={"changes": {object()}},
    )
    await session.exec(sa.text("insert into caller_work (id) values (1)"))
    await session.flush()

    survived = (await session.exec(sa.text("select count(*) from caller_work"))).scalar_one()
    assert survived == 1, "the caller's work is committed even though the audit payload was bad"


async def test_a_result_from_the_wrong_family_fails_where_tests_can_see_it(session, audit_on):  # noqa: ARG001
    """The one error this module does not swallow.

    Everything else here degrades to a warning because losing a row must never
    lose the write it describes. A producer pairing the wrong result is a
    programming error, and swallowing it would trade a wrong row for a missing
    one — equally unauditable, and harder to notice.
    """
    with pytest.raises(ValueError, match="not a result of the 'action' family"):
        await record_audit_event(
            session,
            event=FLOW_UPDATE,
            family=AuditFamily.ACTION,
            result=AuditResult.DENY,
        )

    assert await rows(session) == []


async def test_recording_stages_the_row_and_writes_nothing_of_its_own(session, audit_on):  # noqa: ARG001
    """The row rides the caller's commit, and must not be written ahead of it.

    Flushing here made the audit row the first write in a transaction that still
    had reads ahead of it, and on SQLite that upgrade fails immediately against a
    concurrent writer instead of waiting. It cost the caller the write it was
    only supposed to describe: four simultaneous moves of one flow returned 500
    for 36 of 48 requests with the audit log on, and none at all with it off.
    A savepoint did not contain it, because the lock error deactivates the parent
    transaction along with the savepoint.
    """
    await record_audit_event(session, event=FLOW_UPDATE, family=AuditFamily.ACTION, result=AuditResult.SUCCEEDED)

    staged = [obj for obj in session.new if isinstance(obj, AuditEvent)]
    assert len(staged) == 1, "the row is still pending, waiting on the caller's own commit"


async def test_an_absent_payload_is_sql_null_not_the_json_string_null(session, audit_on):  # noqa: ARG001
    """This table is read with SQL by whoever is investigating.

    A JSON column stores ``None`` as the JSON string "null" by default, which is
    not SQL NULL — so ``where payload is not null`` matches every row and hides
    the ones that actually carry detail. Reading it through the ORM cannot show
    this, because both forms come back as ``None``.
    """
    await record_audit_event(session, event=FLOW_UPDATE, family=AuditFamily.ACTION, result=AuditResult.SUCCEEDED)
    await record_audit_event(
        session,
        event=FLOW_UPDATE,
        family=AuditFamily.ACTION,
        result=AuditResult.SUCCEEDED,
        payload={"changes": ["Agent.model_name"]},
    )
    await session.flush()

    carrying = (
        await session.exec(sa.text("select count(*) from audit_events where payload is not null"))
    ).scalar_one()
    assert carrying == 1, "only the row with a payload is counted as having one"
