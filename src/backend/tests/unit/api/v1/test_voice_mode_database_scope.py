"""Voice credential reads must release their connection before audio processing."""

from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from langflow.api.v1 import voice_mode
from langflow.services.database.models.variable.model import Variable
from langflow.services.variable.constants import GENERIC_TYPE
from langflow.services.variable.service import DatabaseVariableService
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession


@pytest.mark.no_blockbuster
async def test_elevenlabs_credential_read_releases_its_connection(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'voice.db'}")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Variable.__table__.create)
        user_id = uuid4()
        async with AsyncSession(engine, expire_on_commit=False) as session:
            session.add(
                Variable(
                    user_id=user_id,
                    name="ELEVENLABS_API_KEY",
                    value="review-placeholder",
                    type=GENERIC_TYPE,
                    default_fields=[],
                )
            )
            await session.commit()

        class _Database:
            @asynccontextmanager
            async def _with_session(self):
                async with AsyncSession(engine, expire_on_commit=False) as session:
                    yield session

        monkeypatch.setattr("lfx.services.deps.get_db_service", _Database)
        monkeypatch.setattr(voice_mode, "get_variable_service", lambda: DatabaseVariableService(settings_service=None))
        client = await voice_mode.get_or_create_elevenlabs_client(user_id)
        assert client is not None
        assert engine.sync_engine.pool.checkedout() == 0
    finally:
        await engine.dispose()
