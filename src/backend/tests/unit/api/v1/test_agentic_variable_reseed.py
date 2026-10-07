"""Reseeding agentic variables must be idempotent.

The startup path runs on every boot and on every pod. If the existence check cannot
see the rows it created, each restart appends another copy of every agentic variable,
and ``variable`` grows without bound on a serving plane that never cleans it up.
"""

from uuid import uuid4

import pytest
from langflow.api.utils.mcp.agentic_mcp import initialize_agentic_user_variables
from langflow.services.database.models.user.model import User
from langflow.services.database.models.variable.model import Variable
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
