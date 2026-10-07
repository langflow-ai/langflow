"""Real pooled database and HTTP discovery regressions for async model choices."""

import asyncio
import json
import threading
from contextlib import asynccontextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
import pytest_asyncio
from lfx.base.models import model_utils
from lfx.base.models.unified_models import model_catalog
from lfx.services import deps
from lfx.services.variable.request_scope import activate_no_env_fallback, reset_no_env_fallback
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

OWNER = UUID("11111111-1111-1111-1111-111111111111")
OTHER = UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture
def discovery_server(monkeypatch):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.respond({"models": [{"name": "owned-model"}]})

        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            self.respond({"capabilities": ["completion", "tools"]})

        def respond(self, payload):
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "false")
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest_asyncio.fixture
async def pooled_variables(monkeypatch, tmp_path, discovery_server):
    engine = create_async_engine(
        "sqlite+aiosqlite:///" + str(tmp_path / "variables.db"),
        pool_size=1,
        max_overflow=0,
        pool_timeout=0.3,
    )
    async with engine.begin() as connection:
        await connection.execute(text("CREATE TABLE variables (owner TEXT, name TEXT, value TEXT)"))
        await connection.execute(
            text("INSERT INTO variables VALUES (:owner, 'OLLAMA_BASE_URL', :url)"),
            {"owner": str(OWNER), "url": discovery_server},
        )
    observed = []
    pause = asyncio.Event()
    read = asyncio.Event()

    class Database:
        @asynccontextmanager
        async def _with_session(self):
            async with AsyncSession(engine) as session:
                yield session

    class Variables:
        async def get_variables(self, *, user_id, names, field, session):
            assert field == ""
            observed.append(asyncio.get_running_loop())
            rows = await session.execute(
                text("SELECT name, value FROM variables WHERE owner=:owner AND name IN :names").bindparams(
                    bindparam("names", expanding=True)
                ),
                {"owner": str(user_id), "names": sorted(names)},
            )
            read.set()
            if pause.is_set():
                await asyncio.Event().wait()
            return dict(rows.all())

    monkeypatch.setattr(deps, "get_db_service", lambda: Database())
    monkeypatch.setattr(model_utils, "get_variable_service", Variables)
    monkeypatch.setattr(model_catalog, "_get_model_status", AsyncMock(return_value=(set(), set())))
    monkeypatch.setattr(model_catalog, "_fetch_enabled_providers_for_user", AsyncMock(return_value={"Ollama"}))
    policy = SimpleNamespace(allows=lambda p: p == "Ollama", allows_model=lambda *_a, **_kw: True)
    try:
        yield SimpleNamespace(engine=engine, observed=observed, pause=pause, read=read, policy=policy)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_catalog_discovery_waits_on_caller_pool_and_uses_real_http(pooled_variables):
    state = pooled_variables
    held = await state.engine.connect()
    ticks = []

    async def release():
        for _ in range(6):
            await asyncio.sleep(0.01)
            ticks.append(True)
        await held.close()

    release_task = asyncio.create_task(release())
    try:
        options = await asyncio.wait_for(
            model_catalog.aget_language_model_options(OWNER, provider_policy=state.policy), 3
        )
        assert any(option["name"] == "owned-model" for option in options)
        assert state.observed
        assert all(loop is asyncio.get_running_loop() for loop in state.observed)
        assert len(ticks) == 6
        assert state.engine.pool.checkedout() == 0
    finally:
        await release_task
        await held.close()


@pytest.mark.asyncio
async def test_catalog_cancellation_closes_discovery_input_session(pooled_variables):
    state = pooled_variables
    state.pause.set()
    task = asyncio.create_task(model_catalog.aget_language_model_options(OWNER, provider_policy=state.policy))
    await asyncio.wait_for(state.read.wait(), 2)
    assert state.engine.pool.checkedout() == 1
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert state.engine.pool.checkedout() == 0


@pytest.mark.asyncio
async def test_simultaneous_catalogs_preserve_owner_and_no_env_fallback(pooled_variables, monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://server-value-must-not-be-used.invalid")
    token = activate_no_env_fallback(disabled=True)
    try:
        owned, other = await asyncio.gather(
            model_catalog.aget_language_model_options(OWNER, provider_policy=pooled_variables.policy),
            model_catalog.aget_language_model_options(OTHER, provider_policy=pooled_variables.policy),
        )
    finally:
        reset_no_env_fallback(token)
    assert any(option["name"] == "owned-model" for option in owned)
    assert other == []
    assert model_utils._discovery_variables.get() is None


def test_worker_snapshot_cannot_read_another_owner_or_undeclared_variable():
    token = model_utils._discovery_variables.set((str(OWNER), {"OLLAMA_BASE_URL": "owned"}))
    try:
        assert model_utils.get_provider_variable_value(OWNER, "OLLAMA_BASE_URL") == "owned"
        with pytest.raises(ValueError, match="outside its resolved"):
            model_utils.get_provider_variable_value(OTHER, "OLLAMA_BASE_URL")
        with pytest.raises(ValueError, match="outside its resolved"):
            model_utils.get_provider_variable_value(OWNER, "UNDECLARED")
    finally:
        model_utils._discovery_variables.reset(token)


@pytest.mark.asyncio
async def test_discovery_batches_only_enabled_live_provider_variables(pooled_variables, monkeypatch):
    state = pooled_variables
    monkeypatch.setenv("OPENAI_API_KEY", "environment-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://optional-must-not-fall-back.invalid")
    metadata = {
        "Ollama": {"variables": [{"variable_key": "BUNDLE_SETTING"}, {"variable_key": "OLLAMA_BASE_URL"}]},
        "Anthropic": {"variables": [{"variable_key": "ANTHROPIC_API_KEY"}]},
        "OpenRouter": {"variables": [{"variable_key": "DISABLED_PROVIDER_SETTING"}]},
    }
    values = await model_utils.aget_live_model_variables(OWNER, {"Ollama", "OpenAI", "Anthropic"}, metadata)
    assert set(values) == {"OLLAMA_BASE_URL", "BUNDLE_SETTING", "OPENAI_BASE_URL", "OPENAI_API_KEY"}
    assert values["OLLAMA_BASE_URL"].startswith("http://127.0.0.1:")
    assert values["BUNDLE_SETTING"] is None
    assert values["OPENAI_BASE_URL"] is None
    assert values["OPENAI_API_KEY"] == "environment-key"  # pragma: allowlist secret
    assert state.observed == [asyncio.get_running_loop()]
    assert state.engine.pool.checkedout() == 0
