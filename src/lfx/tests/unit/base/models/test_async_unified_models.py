"""Native async model resolution keeps pool release and cancellation on the caller loop."""

import asyncio
import time
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import UUID

import pytest
from lfx.base.models import unified_models as models
from lfx.base.models.unified_models import credentials, instantiation
from lfx.services.variable.request_scope import activate_no_env_fallback, reset_no_env_fallback
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

USER = "11111111-1111-1111-1111-111111111111"
SELECTION = [{"name": "gpt-4o-mini", "provider": "OpenAI", "metadata": {}}]


def allow_policy():
    return SimpleNamespace(require=Mock(), require_model=Mock())


@pytest.mark.asyncio
async def test_native_resolution_releases_a_held_connection_and_preserves_heartbeat(tmp_path, monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///" + str(tmp_path / "provider.db"), pool_size=1, max_overflow=0, pool_timeout=0.15
    )
    held = AsyncSession(engine)
    await held.execute(text("SELECT 1"))
    caller_loop = asyncio.get_running_loop()
    reads = []

    @asynccontextmanager
    async def scope():
        async with AsyncSession(engine) as session:
            yield session

    class Variables:
        async def get_variable(self, *, user_id, name, field, session):
            assert asyncio.get_running_loop() is caller_loop
            assert user_id == UUID(USER)
            assert field == ""
            await session.execute(text("SELECT 1"))
            reads.append(name)
            return "sk-test-owned" if name == "OPENAI_API_KEY" else None

    monkeypatch.setattr(credentials, "session_scope", scope)
    monkeypatch.setattr(credentials, "get_variable_service", Variables)
    monkeypatch.setattr(credentials, "run_until_complete", Mock(side_effect=AssertionError("sync bridge forbidden")))
    monkeypatch.setattr(
        "lfx.services.model_provider_policy.aresolve_model_provider_policy", AsyncMock(return_value=allow_policy())
    )
    monkeypatch.setattr(
        "lfx.services.model_provider_policy.resolve_model_provider_policy",
        Mock(side_effect=AssertionError("sync policy forbidden")),
    )
    factory = Mock(return_value=object())
    monkeypatch.setattr(models, "get_model_class", lambda _name: factory)
    monkeypatch.setattr(instantiation, "_protect_model_connection", Mock())
    ticks = []
    finished = False

    async def heartbeat():
        while not finished:
            ticks.append(time.monotonic())
            await asyncio.sleep(0.005)

    async def commit_release():
        await asyncio.sleep(0.03)
        await held.commit()

    beat = asyncio.create_task(heartbeat())
    release = asyncio.create_task(commit_release())
    token = activate_no_env_fallback(disabled=True)
    try:
        result = await asyncio.wait_for(models.aget_llm(SELECTION, USER, stream=True), timeout=0.5)
        assert result is factory.return_value
        assert len(ticks) >= 3
        assert factory.call_args.kwargs["api_key"] == "sk-test-owned"  # pragma: allowlist secret
        assert "OPENAI_API_KEY" in reads
    finally:
        reset_no_env_fallback(token)
        finished = True
        await beat
        await release
        await held.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_cancellation_returns_lookup_connection_without_constructing_clients(tmp_path, monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///" + str(tmp_path / "cancel.db"), pool_size=1, max_overflow=0, pool_timeout=0.15
    )
    acquired = asyncio.Event()

    @asynccontextmanager
    async def scope():
        async with AsyncSession(engine) as session:
            yield session

    class Variables:
        async def get_variable(self, **kwargs):
            await kwargs["session"].execute(text("SELECT 1"))
            acquired.set()
            await asyncio.Event().wait()

    monkeypatch.setattr(credentials, "session_scope", scope)
    monkeypatch.setattr(credentials, "get_variable_service", Variables)
    monkeypatch.setattr(
        "lfx.services.model_provider_policy.aresolve_model_provider_policy", AsyncMock(return_value=allow_policy())
    )
    constructor = Mock()
    monkeypatch.setattr(models, "get_model_class", constructor)
    task = asyncio.create_task(models.aget_llm(SELECTION, USER))
    try:
        await asyncio.wait_for(acquired.wait(), 0.5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        constructor.assert_not_called()
        async with engine.connect() as connection:
            assert (await connection.execute(text("SELECT 1"))).scalar() == 1
    finally:
        if not task.done():
            task.cancel()
        await engine.dispose()


@pytest.mark.asyncio
async def test_async_policy_denial_precedes_credentials_and_provider_import(monkeypatch):
    policy = allow_policy()
    policy.require.side_effect = PermissionError("provider denied")
    monkeypatch.setattr(
        "lfx.services.model_provider_policy.aresolve_model_provider_policy", AsyncMock(return_value=policy)
    )
    key = AsyncMock(side_effect=AssertionError("credential access before policy"))
    constructor = Mock(side_effect=AssertionError("provider import before policy"))
    monkeypatch.setattr(models, "aget_api_key_for_provider", key)
    monkeypatch.setattr(models, "get_model_class", constructor)
    with pytest.raises(PermissionError, match="provider denied"):
        await models.aget_llm(SELECTION, USER)
    key.assert_not_awaited()
    constructor.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "resolver", [credentials.aget_api_key_for_provider, credentials.aget_all_variables_for_provider]
)
async def test_async_lookup_errors_do_not_use_server_environment(monkeypatch, resolver):
    @asynccontextmanager
    async def scope():
        yield object()

    class Variables:
        async def get_variable(self, **_kwargs):
            msg = "lookup failed"
            raise TimeoutError(msg)

    monkeypatch.setattr(credentials, "session_scope", scope)
    monkeypatch.setattr(credentials, "get_variable_service", Variables)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-server-must-not-fallback")
    with pytest.raises(TimeoutError, match="lookup failed"):
        await resolver(USER, "OpenAI")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider", "variables"),
    [
        ("OpenAI", {"OPENAI_BASE_URL": "https://model.example/v1"}),
        ("Anthropic", {}),
        ("Ollama", {"OLLAMA_BASE_URL": "https://model.example"}),
        ("IBM WatsonX", {"WATSONX_URL": "https://model.example", "WATSONX_PROJECT_ID": "test-project"}),
        ("OpenRouter", {"OPENROUTER_SITE_URL": "https://app.example", "OPENROUTER_SITE_NAME": "test-app"}),
        ("Azure AI Foundry", {"AZURE_AI_FOUNDRY_ENDPOINT": "https://example.services.ai.azure.com/openai/v1"}),
    ],
)
async def test_async_and_sync_construction_preserve_provider_parameters(monkeypatch, provider, variables):
    selection = [
        {"name": "test-model", "provider": provider, "metadata": {"model_class": "UntrustedClass", "reasoning": True}}
    ]
    monkeypatch.setattr(models, "get_api_key_for_provider", Mock(return_value="sk-test"))
    monkeypatch.setattr(models, "aget_api_key_for_provider", AsyncMock(return_value="sk-test"))
    monkeypatch.setattr(models, "get_all_variables_for_provider", Mock(return_value=variables))
    monkeypatch.setattr(models, "aget_all_variables_for_provider", AsyncMock(return_value=variables))
    requested = []

    def model_class(name):
        requested.append(name)
        return lambda **kwargs: kwargs

    monkeypatch.setattr(models, "get_model_class", model_class)
    protect = Mock()
    monkeypatch.setattr(instantiation, "_protect_model_connection", protect)
    policy = allow_policy()
    token = activate_no_env_fallback(disabled=True)
    try:
        sync = models.get_llm(
            selection,
            USER,
            temperature=0.7,
            max_tokens=17,
            stream=True,
            provider_policy=policy,
            overrides={"top_p": 0.9},
        )
        asynchronous = await models.aget_llm(
            selection,
            USER,
            temperature=0.7,
            max_tokens=17,
            stream=True,
            provider_policy=policy,
            overrides={"top_p": 0.9},
        )
    finally:
        reset_no_env_fallback(token)
    assert asynchronous == sync
    assert requested[0] == requested[1]
    assert requested[0] != "UntrustedClass"
    assert "temperature" not in asynchronous
    assert asynchronous["streaming"] is True
    assert asynchronous["top_p"] == 0.9
    assert protect.call_count == 2


@pytest.mark.asyncio
async def test_async_model_inputs_are_fresh_on_each_retry(monkeypatch):
    monkeypatch.setattr(models, "aget_api_key_for_provider", AsyncMock(side_effect=["sk-first", "sk-second"]))
    monkeypatch.setattr(
        models,
        "aget_all_variables_for_provider",
        AsyncMock(
            side_effect=[
                {"OPENAI_BASE_URL": "https://first.example/v1"},
                {"OPENAI_BASE_URL": "https://second.example/v1"},
            ]
        ),
    )
    monkeypatch.setattr(models, "get_model_class", lambda _name: lambda **kwargs: kwargs)
    monkeypatch.setattr(instantiation, "_protect_model_connection", Mock())
    policy = allow_policy()
    first = await models.aget_llm(SELECTION, USER, provider_policy=policy)
    second = await models.aget_llm(SELECTION, USER, provider_policy=policy)
    assert first["api_key"] == "sk-first"  # pragma: allowlist secret
    assert second["api_key"] == "sk-second"  # pragma: allowlist secret
    assert first["base_url"] != second["base_url"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider", "options"),
    [
        ("OpenAI", {"overrides": {"base_url": "http://169.254.169.254/latest/meta-data/"}}),
        ("Ollama", {"ollama_base_url": "http://127.0.0.1:11434"}),
    ],
)
async def test_async_construction_keeps_final_endpoint_ssrf_checks(monkeypatch, provider, options):
    monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
    monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED", "true")
    monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_ALLOW_LOOPBACK", "false")
    monkeypatch.setattr(models, "aget_api_key_for_provider", AsyncMock(return_value="sk-test"))
    monkeypatch.setattr(models, "aget_all_variables_for_provider", AsyncMock(return_value={}))
    constructor = Mock()
    monkeypatch.setattr(models, "get_model_class", lambda _name: constructor)
    selection = [{"name": "test-model", "provider": provider, "metadata": {}}]
    with pytest.raises(ValueError, match="SSRF Protection"):
        await models.aget_llm(selection, USER, provider_policy=allow_policy(), **options)
    constructor.assert_not_called()


@pytest.mark.asyncio
async def test_async_credentials_keep_owner_and_request_context_boundaries(monkeypatch):
    from contextvars import ContextVar

    owner = ContextVar("test-owner")

    @asynccontextmanager
    async def scope():
        yield object()

    class Variables:
        async def get_variable(self, *, user_id, name, **_kwargs):
            await asyncio.sleep(0)
            assert user_id == owner.get()
            return str(user_id) if name == "OPENAI_API_KEY" else None

    monkeypatch.setattr(credentials, "session_scope", scope)
    monkeypatch.setattr(credentials, "get_variable_service", Variables)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-server-not-the-tenant")

    async def resolve(user):
        user = UUID(user)
        token = owner.set(user)
        env_token = activate_no_env_fallback(disabled=True)
        try:
            return await credentials.aget_api_key_for_provider(user, "OpenAI")
        finally:
            reset_no_env_fallback(env_token)
            owner.reset(token)

    users = [USER, "22222222-2222-2222-2222-222222222222"]
    assert await asyncio.gather(*(resolve(user) for user in users)) == users


@pytest.mark.asyncio
@pytest.mark.parametrize("key", ["DATABASE_URL", "LANGFLOW_SECRET_KEY", "OPENAI_BASE_URL"])
async def test_async_key_resolution_cannot_read_reserved_or_nonsecret_variables(monkeypatch, key):
    monkeypatch.setenv(key, "sensitive-not-a-bearer-key")
    assert await credentials.aget_api_key_for_provider(None, "OpenAI", key) is None


def test_sync_resolver_stop_iteration_is_an_error_not_a_model(monkeypatch):
    monkeypatch.setattr(models, "get_api_key_for_provider", Mock(side_effect=StopIteration("resolver exhausted")))
    constructor = Mock()
    monkeypatch.setattr(models, "get_model_class", constructor)
    with pytest.raises(StopIteration, match="resolver exhausted"):
        models.get_llm(SELECTION, USER, provider_policy=allow_policy())
    constructor.assert_not_called()
