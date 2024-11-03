import asyncio

import pytest
from asgi_lifespan import LifespanManager


async def test_database_initialization(benchmark):
    """Test database initialization performance."""

    async def init_db():
        from langflow.main import create_app
        from langflow.services.deps import get_db_service

        await asyncio.to_thread(create_app)
        return get_db_service()

    result = benchmark(init_db)
    assert result is not None


@pytest.mark.benchmark
async def test_app_startup():
    """Test application startup performance."""
    from langflow.main import create_app

    app = await asyncio.to_thread(create_app)
    async with LifespanManager(app):
        assert app is not None
