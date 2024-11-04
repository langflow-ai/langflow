import asyncio

import pytest
from asgi_lifespan import LifespanManager


@pytest.mark.benchmark
async def test_database_initialization():
    """Test database initialization performance."""

    async def init_db():
        from langflow.main import create_app
        from langflow.services.deps import get_db_service

        await asyncio.to_thread(create_app)
        return get_db_service()

    result = await init_db()
    assert result is not None


@pytest.mark.benchmark
async def test_app_startup(monkeypatch, tmp_path):
    """Test application startup performance."""

    async def init_app():
        from langflow.main import create_app

        monkeypatch.setenv("LANGFLOW_DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
        app = await asyncio.to_thread(create_app)
        async with LifespanManager(app):
            return app

    app = await init_app()
    assert app is not None
    monkeypatch.undo()
