import asyncio
import shutil
import tempfile
from contextlib import suppress
from pathlib import Path

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from langflow.services.deps import get_db_service


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
async def test_app_startup(
    monkeypatch,
    request,
    load_flows_dir,
):
    """Test application startup performance."""
    # Set the database url to a test database

    def init_app():
        db_dir = tempfile.mkdtemp()
        db_path = Path(db_dir) / "test.db"
        monkeypatch.setenv("LANGFLOW_DATABASE_URL", f"sqlite:///{db_path}")
        monkeypatch.setenv("LANGFLOW_AUTO_LOGIN", "false")
        if "load_flows" in request.keywords:
            shutil.copyfile(
                pytest.BASIC_EXAMPLE_PATH, Path(load_flows_dir) / "c54f9130-f2fa-4a3e-b22a-3856d946351b.json"
            )
            monkeypatch.setenv("LANGFLOW_LOAD_FLOWS_PATH", load_flows_dir)
            monkeypatch.setenv("LANGFLOW_AUTO_LOGIN", "true")

        from langflow.main import create_app

        app = create_app()
        db_service = get_db_service()
        db_service.database_url = f"sqlite:///{db_path}"
        db_service.reload_engine()
        return app, db_path

    app, db_path = await asyncio.to_thread(init_app)
    # app.dependency_overrides[get_session] = get_session_override
    async with (
        LifespanManager(app, startup_timeout=None, shutdown_timeout=None) as manager,
        AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://testserver/", http2=True) as client,
    ):
        assert client is not None
    # app.dependency_overrides.clear()
    monkeypatch.undo()
    # clear the temp db
    with suppress(FileNotFoundError):
        db_path.unlink()
