"""Reseeding agentic variables must be idempotent.

The startup path runs on every boot and on every pod. If the existence check cannot
see the rows it created, each restart appends another copy of every agentic variable,
and ``variable`` grows without bound on a serving plane that never cleans it up.
"""

import asyncio
import os
from collections import Counter
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from langflow.api.utils.mcp import agentic_mcp
from langflow.api.utils.mcp.agentic_mcp import initialize_agentic_global_variables, initialize_agentic_user_variables
from langflow.services.database.models.user.model import User
from langflow.services.database.models.variable.model import Variable
from langflow.services.deps import get_variable_service, session_scope
from langflow.services.variable.constants import GENERIC_TYPE
from lfx.services.settings.constants import AGENTIC_VARIABLES
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession


async def _seed_user(session) -> User:
    user = User(id=uuid4(), username=f"agentic-{uuid4().hex[:8]}", password="x", is_active=True)  # noqa: S106
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def _variable_names(session, user_id) -> list[str]:
    rows = (await session.exec(select(Variable).where(Variable.user_id == user_id))).all()
    return [row.name for row in rows]


@pytest.mark.asyncio
async def test_should_seed_agentic_variables_on_first_boot(async_session):
    """A fresh installation gets exactly one row per agentic variable."""
    user = await _seed_user(async_session)

    await initialize_agentic_user_variables(user.id, async_session)
    await async_session.commit()

    names = await _variable_names(async_session, user.id)
    assert sorted(names) == sorted(AGENTIC_VARIABLES)


@pytest.mark.asyncio
async def test_should_insert_nothing_when_reseeding_a_seeded_installation(async_session):
    """A second boot against a seeded database must insert zero rows."""
    user = await _seed_user(async_session)

    await initialize_agentic_user_variables(user.id, async_session)
    await async_session.commit()
    after_first = await _variable_names(async_session, user.id)

    await initialize_agentic_user_variables(user.id, async_session)
    await async_session.commit()
    after_second = await _variable_names(async_session, user.id)

    assert sorted(after_second) == sorted(after_first)
    assert len(after_second) == len(AGENTIC_VARIABLES)


@pytest.mark.asyncio
async def test_should_stay_flat_across_repeated_restarts(async_session):
    """Growth is slow and invisible in a short test unless several boots are simulated."""
    user = await _seed_user(async_session)

    for _ in range(5):
        await initialize_agentic_user_variables(user.id, async_session)
        await async_session.commit()

    names = await _variable_names(async_session, user.id)
    assert len(names) == len(AGENTIC_VARIABLES)


@pytest.mark.asyncio
async def test_global_startup_keeps_empty_generic_defaults_across_restarts(async_session):
    """Repeated global startup preserves each empty assistant variable once."""
    user = await _seed_user(async_session)

    for _ in range(3):
        await initialize_agentic_global_variables(async_session)
        await async_session.commit()

    assert sorted(await _variable_names(async_session, user.id)) == ["COMPONENT_ID", "FIELD_NAME", "FLOW_ID"]


@pytest.mark.no_blockbuster
@pytest.mark.asyncio
async def test_global_startup_empty_agentic_variables_can_be_read_and_edited(client, active_user):
    """Owners can find and edit seeded placeholders without creating duplicate rows."""
    async with session_scope() as session:
        await initialize_agentic_global_variables(session)
        seeded_variables = {
            variable.name: str(variable.id)
            for variable in (await session.exec(select(Variable).where(Variable.user_id == active_user.id))).all()
        }
        session.add(
            Variable(user_id=active_user.id, name="EMPTY_OTHER", value="", type=GENERIC_TYPE, default_fields=[])
        )

    assert set(seeded_variables) == {"FLOW_ID", "COMPONENT_ID", "FIELD_NAME"}
    login = await client.post(
        "api/v1/login",
        data={"username": active_user.username, "password": "testpassword"},  # pragma: allowlist secret
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = await client.get("api/v1/variables/", headers=headers)
    assert response.status_code == 200
    variables = {variable["name"]: variable for variable in response.json()}
    assert "EMPTY_OTHER" not in variables

    for name, variable_id in seeded_variables.items():
        variable = variables[name]
        assert variable["id"] == variable_id
        assert variable["type"] == GENERIC_TYPE
        assert variable["value"] == ""
        assert variable["has_value"] is False
        update = await client.patch(
            f"api/v1/variables/{variable['id']}",
            json={"id": variable["id"], "value": f"configured-{name}"},
            headers=headers,
        )
        assert update.status_code == 200
        assert update.json()["id"] == variable["id"]
        assert update.json()["value"] == f"configured-{name}"
        assert update.json()["has_value"] is True

    async with session_scope() as session:
        names = await _variable_names(session, active_user.id)
    assert all(names.count(name) == 1 for name in seeded_variables)


@pytest.fixture(params=["sqlite", "postgres"])
async def agentic_engine(request, tmp_path):
    """A real file-backed SQLite (WAL, like the app) or an isolated PostgreSQL schema."""
    admin = None
    namespace = None
    if request.param == "postgres":
        raw = os.environ.get("LANGFLOW_TEST_POSTGRES_URL")
        if not raw:
            pytest.skip("set LANGFLOW_TEST_POSTGRES_URL for real PostgreSQL coverage")
        pytest.importorskip("psycopg")
        url = sa.make_url(raw).set(drivername="postgresql+psycopg")
        admin = create_async_engine(url)
        namespace = f"agentic_vars_{uuid4().hex}"
        async with admin.begin() as connection:
            await connection.execute(sa.schema.CreateSchema(namespace))
        engine = create_async_engine(url.update_query_dict({"options": f"-csearch_path={namespace}"}))
    else:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'agentic.db'}")

        @sa.event.listens_for(engine.sync_engine, "connect")
        def _sqlite_pragmas(dbapi_connection, _record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode = WAL")
            cursor.execute("PRAGMA busy_timeout = 30000")
            cursor.close()

    try:
        async with engine.begin() as connection:
            await connection.run_sync(SQLModel.metadata.create_all)
        yield engine
    finally:
        await engine.dispose()
        if admin is not None:
            async with admin.begin() as connection:
                await connection.execute(sa.schema.DropSchema(namespace, cascade=True))
            await admin.dispose()


async def _seed_users(engine, count: int) -> list[UUID]:
    users = [
        User(id=uuid4(), username=f"agentic-{uuid4().hex[:8]}", password="x", is_active=True)  # noqa: S106
        for _ in range(count)
    ]
    async with AsyncSession(engine, expire_on_commit=False) as session:
        session.add_all(users)
        await session.commit()
    return [user.id for user in users]


async def _boot(engine) -> None:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        await initialize_agentic_global_variables(session)
        await session.commit()


async def _rows(engine) -> list[Variable]:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        return list((await session.exec(select(Variable))).all())


def _counts(rows: list[Variable]) -> Counter:
    return Counter((row.user_id, row.name) for row in rows)


@pytest.mark.asyncio
async def test_should_keep_one_row_per_user_and_name_across_boots_and_logins(agentic_engine):
    user_ids = await _seed_users(agentic_engine, 2)

    for _ in range(5):
        await _boot(agentic_engine)
        async with AsyncSession(agentic_engine, expire_on_commit=False) as session:
            await initialize_agentic_user_variables(user_ids[0], session)
            await session.commit()

    counts = _counts(await _rows(agentic_engine))
    assert set(counts.values()) == {1}
    assert {name for user_id, name in counts if user_id == user_ids[1]} == {"FLOW_ID", "COMPONENT_ID", "FIELD_NAME"}
    assert {name for user_id, name in counts if user_id == user_ids[0]} == {
        "FLOW_ID",
        "COMPONENT_ID",
        "FIELD_NAME",
        "ASTRA_TOKEN",
    }


@pytest.mark.asyncio
async def test_should_preserve_user_values_and_isolate_users_when_reseeding(agentic_engine):
    edited, fresh = await _seed_users(agentic_engine, 2)
    async with AsyncSession(agentic_engine, expire_on_commit=False) as session:
        session.add(Variable(user_id=edited, name="FLOW_ID", value="edited-flow", type=GENERIC_TYPE, default_fields=[]))
        session.add(Variable(user_id=edited, name="COMPONENT_ID", value="", type=GENERIC_TYPE, default_fields=[]))
        await session.commit()

    for _ in range(3):
        await _boot(agentic_engine)

    rows = await _rows(agentic_engine)
    assert set(_counts(rows).values()) == {1}
    values = {(row.user_id, row.name): row.value for row in rows}
    assert values[edited, "FLOW_ID"] == "edited-flow"
    assert values[edited, "COMPONENT_ID"] == ""
    assert {name for user_id, name in values if user_id == fresh} == {"FLOW_ID", "COMPONENT_ID", "FIELD_NAME"}
    assert len(rows) == 6


@pytest.mark.asyncio
async def test_should_create_one_row_per_name_when_two_workers_initialize_at_once(agentic_engine, monkeypatch):
    """Both workers reach the existence check before either inserts, as two pods booting together do."""
    user_ids = await _seed_users(agentic_engine, 3)
    variable_service = get_variable_service()
    list_variables = variable_service.list_variables
    first_reads: dict[UUID, int] = {}
    both_read: dict[UUID, asyncio.Event] = {}

    async def list_variables_after_rendezvous(user_id, session):
        key = UUID(str(user_id))
        arrival = first_reads[key] = first_reads.get(key, 0) + 1
        result = await list_variables(user_id, session)
        # Only each worker's first, unlocked read joins the rendezvous; locked rechecks pass straight through.
        if arrival <= 2:
            both_read.setdefault(key, asyncio.Event())
            if arrival == 2:
                both_read[key].set()
            # Never proceeds alone: a missed rendezvous surfaces as a swallowed error and fails the test.
            await asyncio.wait_for(both_read[key].wait(), timeout=30)
        return result

    monkeypatch.setattr(variable_service, "list_variables", list_variables_after_rendezvous)
    # The initializer logs and swallows per-user errors, so a worker that failed would otherwise look fine.
    swallowed_errors = []

    async def record_error(message, *args, **kwargs):  # noqa: ARG001
        swallowed_errors.append(message)

    monkeypatch.setattr(agentic_mcp.logger, "aexception", record_error)

    results = await asyncio.gather(_boot(agentic_engine), _boot(agentic_engine), return_exceptions=True)

    assert not [result for result in results if isinstance(result, BaseException)]
    assert swallowed_errors == []
    counts = _counts(await _rows(agentic_engine))
    assert set(counts.values()) == {1}
    assert len(counts) == 3 * len(user_ids)


@pytest.mark.asyncio
async def test_should_roll_back_only_the_failing_user_and_seed_the_rest(agentic_engine, monkeypatch):
    """Each user is seeded in its own transaction, so one user's database error cannot undo or block another."""
    failing, healthy = await _seed_users(agentic_engine, 2)
    variable_service = get_variable_service()
    create_variable = variable_service.create_variable

    async def create_variable_then_fail_flush(user_id, name, value, **kwargs):
        variable = await create_variable(user_id, name, value, **kwargs)
        if user_id == failing and name == "FLOW_ID":
            session = kwargs["session"]
            session.expunge(variable)
            session.add(Variable(id=variable.id, user_id=failing, name="DUPLICATE_KEY", value="", type=GENERIC_TYPE))
            await session.flush()
        return variable

    monkeypatch.setattr(variable_service, "create_variable", create_variable_then_fail_flush)
    await _boot(agentic_engine)

    counts = _counts(await _rows(agentic_engine))
    assert counts == Counter({(healthy, "FLOW_ID"): 1, (healthy, "COMPONENT_ID"): 1, (healthy, "FIELD_NAME"): 1})

    monkeypatch.setattr(variable_service, "create_variable", create_variable)
    await _boot(agentic_engine)
    counts = _counts(await _rows(agentic_engine))
    assert set(counts.values()) == {1}
    assert {user_id for user_id, _ in counts} == {failing, healthy}
    assert len(counts) == 6


@pytest.mark.asyncio
async def test_should_leave_existing_duplicates_untouched(agentic_engine):
    """Historical duplicates may hold user values; startup neither deletes them nor adds more."""
    (user_id,) = await _seed_users(agentic_engine, 1)
    async with AsyncSession(agentic_engine, expire_on_commit=False) as session:
        session.add(Variable(user_id=user_id, name="FLOW_ID", value="", type=GENERIC_TYPE, default_fields=[]))
        session.add(Variable(user_id=user_id, name="FLOW_ID", value="kept", type=GENERIC_TYPE, default_fields=[]))
        await session.commit()
    before = {row.id: row.value for row in await _rows(agentic_engine)}

    await _boot(agentic_engine)
    await _boot(agentic_engine)

    rows = await _rows(agentic_engine)
    assert {row.id: row.value for row in rows if row.name == "FLOW_ID"} == before
    assert _counts(rows) == Counter({(user_id, "FLOW_ID"): 2, (user_id, "COMPONENT_ID"): 1, (user_id, "FIELD_NAME"): 1})
