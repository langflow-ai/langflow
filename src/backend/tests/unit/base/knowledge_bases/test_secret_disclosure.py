"""Knowledge Base credential resolution must not become a secret-read API."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from langflow.api.v1 import knowledge_bases as kb_api
from langflow.schema.knowledge_base import TestBackendConnectionRequest as ConnectionRequest
from lfx.base.knowledge_bases.backends.opensearch import OpenSearchBackend
from lfx.services.deps import get_settings_service
from pydantic import SecretStr


@pytest.mark.parametrize("enabled", [False, True])
async def test_environment_fallback_obeys_settings(monkeypatch, enabled):
    monkeypatch.setattr(get_settings_service().settings, "fallback_to_env_var", enabled)
    monkeypatch.setenv("KB_TEST_VALUE", "synthetic-credential")
    backend = OpenSearchBackend(kb_name="test")
    expected = ("synthetic-credential", "environment") if enabled else (None, "missing")
    assert await backend.resolve_secret_with_source("KB_TEST_VALUE") == expected


async def test_environment_fallback_fails_closed_without_settings(monkeypatch):
    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: None)
    monkeypatch.setenv("KB_TEST_VALUE", "synthetic-credential")
    assert await OpenSearchBackend(kb_name="test").resolve_secret_with_source("KB_TEST_VALUE") == (None, "missing")


async def test_enabled_fallback_still_blocks_reserved_variables(monkeypatch):
    monkeypatch.setattr(get_settings_service().settings, "fallback_to_env_var", True)
    monkeypatch.setenv("LANGFLOW_SECRET_KEY", "synthetic-credential")
    assert await OpenSearchBackend(kb_name="test").resolve_secret_with_source("LANGFLOW_SECRET_KEY") == (
        None,
        "missing",
    )


async def test_user_variable_still_resolves_with_environment_fallback_disabled(monkeypatch):
    monkeypatch.setattr(get_settings_service().settings, "fallback_to_env_var", False)
    monkeypatch.setenv("KB_TEST_VALUE", "environment-value")
    user_id = uuid4()
    session = object()
    service = SimpleNamespace(get_variable=AsyncMock(return_value=SecretStr("tenant-value")))

    @asynccontextmanager
    async def scope():
        yield session

    monkeypatch.setattr("lfx.services.deps.get_variable_service", lambda: service)
    monkeypatch.setattr("lfx.services.deps.session_scope", scope)
    backend = OpenSearchBackend(kb_name="test", user_id=user_id)
    assert await backend.resolve_secret_with_source("KB_TEST_VALUE") == ("tenant-value", "variable")
    service.get_variable.assert_awaited_once_with(user_id=user_id, name="KB_TEST_VALUE", field="", session=session)


@pytest.mark.parametrize("create", [False, True])
@pytest.mark.parametrize(
    "value",
    [
        "synthetic-credential",
        "https://user:synthetic-credential@example.invalid/42",  # pragma: allowlist secret
        "amqp://user:synthetic-credential@example.invalid",  # pragma: allowlist secret
        "https://[synthetic-credential",
    ],
)
async def test_connection_and_create_do_not_echo_resolved_values(monkeypatch, tmp_path, create, value):
    monkeypatch.setattr(get_settings_service().settings, "fallback_to_env_var", True)
    monkeypatch.setenv("KB_TEST_VALUE", value)
    monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
    monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED", "true")
    backend = OpenSearchBackend(kb_name="test", backend_config={"url_variable": "KB_TEST_VALUE"})
    monkeypatch.setattr(kb_api, "create_backend", lambda *_args, **_kwargs: backend)
    monkeypatch.setattr(kb_api, "_guard_kb_action", AsyncMock())
    user = SimpleNamespace(id=uuid4())
    if create:
        with pytest.raises(HTTPException) as caught:
            await kb_api._validate_create_backend(
                backend_type="opensearch", backend_config={}, kb_name="test", kb_path=tmp_path, user_id=user.id
            )
        assert caught.value.status_code == 422
        rendered = str(caught.value.detail)
    else:
        result = await kb_api.test_backend_connection(
            ConnectionRequest(backend_type="opensearch", backend_config={"url_variable": "KB_TEST_VALUE"}), user
        )
        assert not result.ok
        assert result.details["type"] == "SSRFProtectionError"
        rendered = result.model_dump_json()
    assert "synthetic-credential" not in rendered
    assert "KB_TEST_VALUE" in rendered


@pytest.mark.usefixtures("fake_opensearchpy")
@pytest.mark.parametrize("stage", ["setup", "connection", "authentication", "authorization", "tls", "other"])
async def test_sdk_errors_do_not_echo_credentials(stage):
    from opensearchpy.exceptions import AuthenticationException, AuthorizationException, SSLError
    from opensearchpy.exceptions import ConnectionError as OpenSearchConnectionError

    backend = OpenSearchBackend(kb_name="test", backend_config={"index_name": "test-index"})
    backend._secrets_resolved = True
    backend._resolved_url = "https://example.invalid"
    backend._resolved_username = None
    backend._resolved_password = None
    errors = {
        "setup": ValueError("synthetic-credential"),
        "connection": OpenSearchConnectionError("N/A", "synthetic-credential", {}),
        "authentication": AuthenticationException(401, "synthetic-credential", {}),
        "authorization": AuthorizationException(403, "synthetic-credential", {}),
        "tls": SSLError("N/A", "synthetic-credential", {}),
        "other": RuntimeError("synthetic-credential"),
    }
    client = MagicMock()
    client.info.side_effect = errors[stage]
    with (
        patch("opensearchpy.OpenSearch", side_effect=errors[stage] if stage == "setup" else None, return_value=client),
        patch("langchain_community.vectorstores.OpenSearchVectorSearch"),
    ):
        result = await backend.test_connection()
    assert result.ok is (stage == "authorization")
    assert "synthetic-credential" not in str(result)
