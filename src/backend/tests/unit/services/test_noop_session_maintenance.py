"""Keep no-op and database sessions compatible with maintenance reads."""

import pytest
from langflow.services.database.models.maintenance import MaintenanceState
from langflow.services.database.session import NoopSession as BackendNoopSession
from langflow.services.maintenance.state import maintenance_enabled
from lfx.services.session import NoopSession as LfxNoopSession
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession as SQLAlchemyAsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession


@pytest.mark.parametrize("session_type", [BackendNoopSession, LfxNoopSession])
@pytest.mark.asyncio
async def test_noop_session_maintenance_read(session_type):
    session = session_type()
    statement = select(MaintenanceState.enabled)

    assert (await session.exec(statement)).first() is None
    assert (await session.exec(statement)).all() == []
    assert (await session.execute(statement)).scalars().first() is None
    assert (await session.execute(statement)).scalars().all() == []
    assert await maintenance_enabled(session) is False


@pytest.mark.parametrize("session_type", [SQLAlchemyAsyncSession, SQLModelAsyncSession])
@pytest.mark.asyncio
async def test_maintenance_read_with_real_async_sessions(session_type):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(MaintenanceState.__table__.create)
        async with session_type(engine) as session:
            assert await maintenance_enabled(session) is False
            session.add(MaintenanceState(id=1, enabled=True))
            await session.commit()
            assert await maintenance_enabled(session) is True
            row = await session.get(MaintenanceState, 1)
            row.enabled = False
            await session.commit()
            assert await maintenance_enabled(session) is False
        async with engine.begin() as connection:
            await connection.run_sync(MaintenanceState.__table__.drop)
        async with session_type(engine) as session:
            with pytest.raises(SQLAlchemyError):
                await maintenance_enabled(session)
    finally:
        await engine.dispose()
