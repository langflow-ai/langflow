"""Watsonx Orchestrate local development URL and auth helpers."""

from types import SimpleNamespace

import pytest
from langflow.services.adapters.deployment.watsonx_orchestrate.client import resolve_wxo_authenticator
from langflow.services.adapters.deployment.watsonx_orchestrate.local_dev import (
    StaticJwtAuthenticator,
    is_wxo_local_instance_url,
    resolve_wxo_local_bearer_token,
    wxo_local_gateway_origin,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.types import WxOClient
from langflow.services.database.models.deployment_provider_account.schemas import DeploymentProviderKey
from langflow.services.database.models.deployment_provider_account.utils import (
    check_provider_url_allowed,
    validate_provider_url,
)
from lfx.services.adapters.deployment.exceptions import AuthSchemeError


class _Info:
    field_name = "provider_url"


def test_validate_provider_url_rejects_http_without_local_dev_flag(monkeypatch):
    monkeypatch.delenv("LANGFLOW_WXO_LOCAL_DEV", raising=False)
    with pytest.raises(ValueError, match="https"):
        validate_provider_url("http://localhost:4321/", _Info())


def test_validate_provider_url_accepts_http_localhost_when_local_dev(monkeypatch):
    monkeypatch.setenv("LANGFLOW_WXO_LOCAL_DEV", "true")
    out = validate_provider_url("http://LOCALHOST:4321/orchestrate", _Info())
    assert out == "http://localhost:4321/orchestrate"


def test_check_provider_url_allowed_localhost_when_local_dev(monkeypatch):
    monkeypatch.setenv("LANGFLOW_WXO_LOCAL_DEV", "true")
    check_provider_url_allowed("http://127.0.0.1:4321/", DeploymentProviderKey.WATSONX_ORCHESTRATE)


def test_check_provider_url_allowed_rejects_localhost_without_flag(monkeypatch):
    monkeypatch.delenv("LANGFLOW_WXO_LOCAL_DEV", raising=False)
    with pytest.raises(ValueError, match="not allowed"):
        check_provider_url_allowed("http://localhost:4321/", DeploymentProviderKey.WATSONX_ORCHESTRATE)


def test_is_wxo_local_instance_url():
    assert is_wxo_local_instance_url("http://localhost:1/x") is True
    assert is_wxo_local_instance_url("https://api.foo.ibm.com/x") is False


def test_is_wxo_local_instance_url_extra_hosts(monkeypatch):
    monkeypatch.setenv("LANGFLOW_WXO_LOCAL_INSTANCE_HOSTS", "host.docker.internal, my-wxo.local")
    assert is_wxo_local_instance_url("http://host.docker.internal:4321/") is True
    assert is_wxo_local_instance_url("http://MY-WXO.LOCAL:1/x") is True
    assert is_wxo_local_instance_url("https://api.foo.ibm.com/x") is False


def test_validate_provider_url_accepts_http_extra_host_when_local_dev(monkeypatch):
    monkeypatch.setenv("LANGFLOW_WXO_LOCAL_DEV", "true")
    monkeypatch.setenv("LANGFLOW_WXO_LOCAL_INSTANCE_HOSTS", "host.docker.internal")
    out = validate_provider_url("http://host.docker.internal:4321/", _Info())
    assert out == "http://host.docker.internal:4321/"


def test_check_provider_url_allowed_extra_host_when_local_dev(monkeypatch):
    monkeypatch.setenv("LANGFLOW_WXO_LOCAL_DEV", "true")
    monkeypatch.setenv("LANGFLOW_WXO_LOCAL_INSTANCE_HOSTS", "host.docker.internal")
    check_provider_url_allowed(
        "http://host.docker.internal:4321/",
        DeploymentProviderKey.WATSONX_ORCHESTRATE,
    )


def test_resolve_wxo_authenticator_extra_local_host_uses_static_jwt(monkeypatch):
    monkeypatch.setenv("LANGFLOW_WXO_LOCAL_DEV", "true")
    monkeypatch.setenv("LANGFLOW_WXO_LOCAL_INSTANCE_HOSTS", "host.docker.internal")
    monkeypatch.setenv("WXO_MCSP_LOCAL_TOKEN", "jwt-for-docker")
    auth = resolve_wxo_authenticator("http://host.docker.internal:4321", api_key="unused")
    assert auth.token_manager.get_token() == "jwt-for-docker"


def test_wxo_client_get_agents_raw_uses_agent_client_on_extra_local_host(monkeypatch):
    monkeypatch.delenv("LANGFLOW_WXO_LOCAL_API_ROOT", raising=False)
    monkeypatch.setenv("LANGFLOW_WXO_LOCAL_INSTANCE_HOSTS", "host.docker.internal")
    client = WxOClient(
        instance_url="http://host.docker.internal:4321",
        authenticator=StaticJwtAuthenticator("t"),
    )
    calls: list[tuple[str, object]] = []

    def fake_agent_get(path, params=None):
        calls.append((path, params))
        return []

    monkeypatch.setattr(client.agent, "_get", fake_agent_get)
    client.get_agents_raw(params={"limit": 2})
    assert calls == [(client.agent.base_endpoint, {"limit": 2})]


def test_resolve_wxo_local_bearer_token_prefers_env(monkeypatch):
    monkeypatch.setenv("LANGFLOW_WXO_LOCAL_DEV", "true")
    monkeypatch.setenv("WXO_MCSP_LOCAL_TOKEN", "from-env")
    assert resolve_wxo_local_bearer_token(api_key="eyJignored") == "from-env"


def test_resolve_wxo_local_bearer_token_falls_back_to_jwt_api_key(monkeypatch):
    monkeypatch.setenv("LANGFLOW_WXO_LOCAL_DEV", "true")
    monkeypatch.delenv("WXO_MCSP_LOCAL_TOKEN", raising=False)
    jwt_like = "eyJhbGciOiJIUzI1NiJ9.e30.sig"
    assert resolve_wxo_local_bearer_token(api_key=jwt_like) == jwt_like


def test_resolve_wxo_authenticator_local_uses_static_jwt(monkeypatch):
    monkeypatch.setenv("LANGFLOW_WXO_LOCAL_DEV", "true")
    monkeypatch.setenv("WXO_MCSP_LOCAL_TOKEN", "test-jwt-token")
    auth = resolve_wxo_authenticator("http://localhost:4321", api_key="unused")
    assert auth.token_manager.get_token() == "test-jwt-token"


def test_resolve_wxo_authenticator_local_requires_bearer(monkeypatch):
    monkeypatch.setenv("LANGFLOW_WXO_LOCAL_DEV", "true")
    monkeypatch.delenv("WXO_MCSP_LOCAL_TOKEN", raising=False)
    with pytest.raises(AuthSchemeError, match="WXO_MCSP_LOCAL_TOKEN"):
        resolve_wxo_authenticator("http://127.0.0.1:1", api_key="not-a-jwt")


def test_resolve_wxo_authenticator_cloud_still_uses_mcsp(monkeypatch):
    monkeypatch.delenv("LANGFLOW_WXO_LOCAL_DEV", raising=False)
    auth = resolve_wxo_authenticator("https://api.dl.watson-orchestrate.ibm.com/instances/x", api_key="k")
    assert auth.__class__.__name__ == "MCSPAuthenticator"


def test_wxo_local_gateway_origin_strips_path():
    assert wxo_local_gateway_origin("http://LOCALHOST:4321/extra") == "http://localhost:4321"


def test_wxo_client_local_developer_edition_base_urls(monkeypatch):
    monkeypatch.delenv("LANGFLOW_WXO_LOCAL_API_ROOT", raising=False)
    client = WxOClient(
        instance_url="http://127.0.0.1:4321",
        authenticator=StaticJwtAuthenticator("t"),
    )
    assert client.tool.base_url == "http://127.0.0.1:4321/api/v1"
    assert client.agent.base_url == "http://127.0.0.1:4321/api/v1"
    assert client.base.base_url == "http://127.0.0.1:4321/api/v1/orchestrate"
    assert client.connections.base_url == "http://127.0.0.1:4321/api/v1"


@pytest.mark.anyio
async def test_create_config_local_developer_edition_unified_connection_payload(monkeypatch):
    """Developer Edition expects CreateConnection (appid, connection_type, credentials, shared)."""
    from ibm_watsonx_orchestrate_core.types.connections import KeyValueConnectionCredentials
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.config import create_config
    from lfx.services.adapters.deployment.schema import DeploymentConfig

    monkeypatch.delenv("LANGFLOW_WXO_LOCAL_API_ROOT", raising=False)
    create_payloads: list[dict] = []

    class FakeConnections:
        def create(self, payload: dict) -> None:
            create_payloads.append(payload)

        def create_config(self, app_id: str, payload: dict) -> None:  # noqa: ARG002
            msg = "create_config must not run for local Developer Edition unified create"
            raise AssertionError(msg)

        def create_credentials(self, *args, **kwargs) -> None:  # noqa: ARG002
            msg = "create_credentials must not run for local Developer Edition unified create"
            raise AssertionError(msg)

    clients = SimpleNamespace(
        instance_url="http://127.0.0.1:4321",
        connections=FakeConnections(),
    )

    async def fake_resolve_runtime_credentials(**kwargs):  # noqa: ARG001
        return KeyValueConnectionCredentials({"VAR": "x"})

    monkeypatch.setattr(
        "langflow.services.adapters.deployment.watsonx_orchestrate.core.config.resolve_runtime_credentials",
        fake_resolve_runtime_credentials,
    )

    app_id = await create_config(
        clients=clients,
        config=DeploymentConfig(name="myapp"),
        user_id="user-1",
        db=SimpleNamespace(),
    )

    assert app_id == "myapp"
    assert create_payloads == [
        {
            "appid": "myapp",
            "connection_type": "key_value_creds",
            "credentials": {"runtime_credentials": {"VAR": "x"}},
            "shared": True,
        },
    ]


def test_wxo_client_get_models_raw_normalizes_resources_envelope(monkeypatch):
    """DE ``/models/list`` returns ``resources`` with ``id``; Langflow expects ``model_name``."""
    monkeypatch.delenv("LANGFLOW_WXO_LOCAL_API_ROOT", raising=False)
    client = WxOClient(
        instance_url="http://127.0.0.1:4321",
        authenticator=StaticJwtAuthenticator("t"),
    )

    def fake_get(path, params=None):  # noqa: ARG001
        return {
            "resources": [
                {"id": "groq/openai/gpt-oss-120b", "label": "GPT-OSS 120B", "type": "Groq"},
                {"id": "watsonx/ibm/granite-3-1-8b-base", "label": "granite", "type": "watsonx.ai"},
            ]
        }

    monkeypatch.setattr(client.tool, "_get", fake_get)
    out = client.get_models_raw()
    assert out == [
        {"model_name": "groq/openai/gpt-oss-120b"},
        {"model_name": "watsonx/ibm/granite-3-1-8b-base"},
    ]


def test_wxo_client_get_models_raw_normalizes_items_envelope(monkeypatch):
    monkeypatch.delenv("LANGFLOW_WXO_LOCAL_API_ROOT", raising=False)
    client = WxOClient(
        instance_url="http://127.0.0.1:4321",
        authenticator=StaticJwtAuthenticator("t"),
    )

    def fake_get(path, params=None):  # noqa: ARG001
        return {"items": [{"id": "watsonx/ibm/granite-3-1-8b-base", "label": "g"}]}

    monkeypatch.setattr(client.tool, "_get", fake_get)
    assert client.get_models_raw() == [{"model_name": "watsonx/ibm/granite-3-1-8b-base"}]


def test_wxo_client_get_models_raw_falls_back_to_models_path_on_404(monkeypatch):
    from types import SimpleNamespace

    from ibm_watsonx_orchestrate_clients.tools.tool_client import ClientAPIException

    monkeypatch.delenv("LANGFLOW_WXO_LOCAL_API_ROOT", raising=False)
    client = WxOClient(
        instance_url="http://127.0.0.1:4321",
        authenticator=StaticJwtAuthenticator("t"),
    )
    paths: list[str] = []

    def fake_get(path, params=None):  # noqa: ARG001
        paths.append(path)
        if path == "/models/list":
            raise ClientAPIException(response=SimpleNamespace(status_code=404))
        if path == "/models":
            return {"resources": [{"id": "from-models"}]}
        msg = f"unexpected path {path}"
        raise AssertionError(msg)

    monkeypatch.setattr(client.tool, "_get", fake_get)
    assert client.get_models_raw() == [{"model_name": "from-models"}]
    assert paths == ["/models/list", "/models"]


def test_wxo_client_get_models_raw_normalizes_nested_data_resources(monkeypatch):
    monkeypatch.delenv("LANGFLOW_WXO_LOCAL_API_ROOT", raising=False)
    client = WxOClient(
        instance_url="http://127.0.0.1:4321",
        authenticator=StaticJwtAuthenticator("t"),
    )

    def fake_get(path, params=None):  # noqa: ARG001
        return {"data": {"resources": [{"id": "watsonx/ibm/granite-3-1-8b-base"}]}}

    monkeypatch.setattr(client.tool, "_get", fake_get)
    assert client.get_models_raw() == [{"model_name": "watsonx/ibm/granite-3-1-8b-base"}]


def test_wxo_client_get_models_raw_uses_models_list_when_local_api_root_env_set(monkeypatch):
    """``LANGFLOW_WXO_LOCAL_API_ROOT`` must not switch catalog fetch to orchestrate ``/models``."""
    monkeypatch.setenv("LANGFLOW_WXO_LOCAL_API_ROOT", "http://127.0.0.1:4321/api/v1")
    client = WxOClient(
        instance_url="http://127.0.0.1:4321",
        authenticator=StaticJwtAuthenticator("t"),
    )
    paths: list[str] = []

    def fake_tool_get(path, params=None):  # noqa: ARG001
        paths.append(path)
        return {"resources": [{"id": "watsonx/x"}]}

    monkeypatch.setattr(client.tool, "_get", fake_tool_get)
    assert client.get_models_raw() == [{"model_name": "watsonx/x"}]
    assert paths == ["/models/list"]


def test_wxo_client_post_model_raw_uses_tool_client_on_loopback(monkeypatch):
    """Developer Edition registers models via POST /api/v1/models on the tool client."""
    monkeypatch.delenv("LANGFLOW_WXO_LOCAL_API_ROOT", raising=False)
    client = WxOClient(
        instance_url="http://127.0.0.1:4321",
        authenticator=StaticJwtAuthenticator("t"),
    )
    posted: list[tuple[str, dict]] = []

    def fake_tool_post(path, data=None, files=None):  # noqa: ARG001
        posted.append((path, data or {}))
        return {"id": "m1"}

    monkeypatch.setattr(client.tool, "_post", fake_tool_post)
    out = client.post_model_raw(data={"name": "my-local", "model_type": "chat"})
    assert out == {"id": "m1"}
    assert posted == [("/models", {"name": "my-local", "model_type": "chat"})]


def test_wxo_client_get_agents_raw_uses_agent_client_on_loopback(monkeypatch):
    """Listing agents must not use BaseWXOClient ``/agents`` when provider URL is loopback."""
    monkeypatch.delenv("LANGFLOW_WXO_LOCAL_API_ROOT", raising=False)
    client = WxOClient(
        instance_url="http://127.0.0.1:4321",
        authenticator=StaticJwtAuthenticator("t"),
    )
    calls: list[tuple[str, object]] = []

    def fake_agent_get(path, params=None):
        calls.append((path, params))
        return []

    monkeypatch.setattr(client.agent, "_get", fake_agent_get)
    client.get_agents_raw(params={"limit": 1})
    assert calls == [(client.agent.base_endpoint, {"limit": 1})]


def test_wxo_client_get_connection_draft_parses_list_response(monkeypatch):
    """Developer Edition may return a JSON array from GET /connections/applications."""
    monkeypatch.delenv("LANGFLOW_WXO_LOCAL_API_ROOT", raising=False)
    client = WxOClient(
        instance_url="http://127.0.0.1:4321",
        authenticator=StaticJwtAuthenticator("t"),
    )

    def fake_get(path, params=None):  # noqa: ARG001
        assert path == "/connections/applications"
        return [{"appid": "flowconn", "connection_id": "c-9"}]

    monkeypatch.setattr(client.connections, "_get", fake_get)
    got = client.get_connection_draft_for_validation("flowconn")
    assert got is not None
    assert got.connection_id == "c-9"
    assert got.app_id == "flowconn"


def test_upload_tool_artifact_bytes_dumps_zip_when_env_set(monkeypatch, tmp_path):
    from unittest.mock import MagicMock

    from langflow.services.adapters.deployment.watsonx_orchestrate.core.tools import upload_tool_artifact_bytes

    monkeypatch.setenv("LANGFLOW_WXO_DUMP_TOOL_ARTIFACTS", str(tmp_path))
    clients = MagicMock()
    clients.upload_tool_artifact.return_value = {"ok": True}
    payload = b"fake-zip"
    upload_tool_artifact_bytes(clients, tool_id="wxo-tool-1", artifact_bytes=payload)
    assert (tmp_path / "wxo-tool-1.zip").read_bytes() == payload


def test_upload_tool_artifact_bytes_skips_dump_when_env_unset(monkeypatch, tmp_path):
    from unittest.mock import MagicMock

    from langflow.services.adapters.deployment.watsonx_orchestrate.core.tools import upload_tool_artifact_bytes

    monkeypatch.delenv("LANGFLOW_WXO_DUMP_TOOL_ARTIFACTS", raising=False)
    clients = MagicMock()
    clients.upload_tool_artifact.return_value = {}
    upload_tool_artifact_bytes(clients, tool_id="t2", artifact_bytes=b"x")
    assert not any(tmp_path.iterdir())
