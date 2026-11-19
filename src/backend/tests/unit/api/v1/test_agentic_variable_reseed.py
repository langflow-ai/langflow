"""Reseeding agentic variables must be idempotent.

The startup path runs on every boot and on every pod. If the existence check cannot
see the rows it created, each restart appends another copy of every agentic variable,
and ``variable`` grows without bound on a serving plane that never cleans it up.
"""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from langflow.api.utils.mcp.agentic_mcp import initialize_agentic_global_variables, initialize_agentic_user_variables
from langflow.services.database.models.user.model import User
from langflow.services.database.models.variable.model import Variable
from langflow.services.deps import session_scope
from langflow.services.variable.constants import GENERIC_TYPE
from lfx.services.settings.constants import AGENTIC_VARIABLES
from sqlmodel import select


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


@pytest.mark.asyncio
async def test_global_startup_preserves_populated_user_values(async_session):
    """Initialization must not overwrite a user-edited placeholder value."""
    user = await _seed_user(async_session)
    edited = Variable(
        user_id=user.id,
        name="FLOW_ID",
        value="user-edited-flow",
        type=GENERIC_TYPE,
        default_fields=[],
    )
    async_session.add(edited)
    await async_session.commit()
    await async_session.refresh(edited)

    await initialize_agentic_global_variables(async_session)
    await async_session.commit()

    rows = (await async_session.exec(select(Variable).where(Variable.user_id == user.id))).all()
    flow_rows = [row for row in rows if row.name == "FLOW_ID"]
    assert len(flow_rows) == 1
    assert flow_rows[0].id == edited.id
    assert flow_rows[0].value == "user-edited-flow"
    assert {row.name for row in rows} == {"COMPONENT_ID", "FIELD_NAME", "FLOW_ID"}


@pytest.mark.asyncio
async def test_global_startup_isolates_placeholders_per_user(async_session):
    """Each user gets their own placeholders; one user's edits stay private."""
    user_a = await _seed_user(async_session)
    user_b = await _seed_user(async_session)
    async_session.add(
        Variable(
            user_id=user_a.id,
            name="FLOW_ID",
            value="only-user-a",
            type=GENERIC_TYPE,
            default_fields=[],
        )
    )
    await async_session.commit()

    await initialize_agentic_global_variables(async_session)
    await async_session.commit()

    rows_a = (await async_session.exec(select(Variable).where(Variable.user_id == user_a.id))).all()
    rows_b = (await async_session.exec(select(Variable).where(Variable.user_id == user_b.id))).all()
    assert sorted(row.name for row in rows_a) == ["COMPONENT_ID", "FIELD_NAME", "FLOW_ID"]
    assert sorted(row.name for row in rows_b) == ["COMPONENT_ID", "FIELD_NAME", "FLOW_ID"]
    assert [row.value for row in rows_a if row.name == "FLOW_ID"] == ["only-user-a"]
    assert [row.value for row in rows_b if row.name == "FLOW_ID"] == [""]


@pytest.mark.asyncio
async def test_global_startup_does_not_delete_historical_duplicates(async_session):
    """Existing conflicting rows must be left untouched; no extra copy is added."""
    user = await _seed_user(async_session)
    empty = Variable(user_id=user.id, name="FLOW_ID", value="", type=GENERIC_TYPE, default_fields=[])
    edited = Variable(
        user_id=user.id,
        name="FLOW_ID",
        value="keep-this-value",
        type=GENERIC_TYPE,
        default_fields=[],
    )
    async_session.add(empty)
    async_session.add(edited)
    await async_session.commit()
    original_ids = {empty.id, edited.id}

    await initialize_agentic_global_variables(async_session)
    await async_session.commit()

    rows = (await async_session.exec(select(Variable).where(Variable.user_id == user.id))).all()
    flow_rows = [row for row in rows if row.name == "FLOW_ID"]
    assert {row.id for row in flow_rows} == original_ids
    assert {row.value for row in flow_rows} == {"", "keep-this-value"}
    names = [row.name for row in rows]
    assert names.count("FLOW_ID") == 2
    assert names.count("COMPONENT_ID") == 1
    assert names.count("FIELD_NAME") == 1


@pytest.mark.asyncio
async def test_existence_check_does_not_trust_list_variables(async_session, monkeypatch):
    """Startup must see empty placeholders even if list_variables hides them."""
    from langflow.services.deps import get_variable_service

    user = await _seed_user(async_session)
    await initialize_agentic_global_variables(async_session)
    await async_session.commit()

    monkeypatch.setattr(get_variable_service(), "list_variables", AsyncMock(return_value=[]))

    await initialize_agentic_global_variables(async_session)
    await async_session.commit()

    names = await _variable_names(async_session, user.id)
    assert names.count("FLOW_ID") == 1
    assert names.count("COMPONENT_ID") == 1
    assert names.count("FIELD_NAME") == 1
    assert len(names) == 3


@pytest.mark.asyncio
async def test_caller_rollback_discards_uncommitted_placeholders(async_session):
    """Initialization flushes through the caller's session and honors rollback."""
    user = await _seed_user(async_session)
    user_id = user.id

    await initialize_agentic_global_variables(async_session)
    await async_session.rollback()

    assert await _variable_names(async_session, user_id) == []
