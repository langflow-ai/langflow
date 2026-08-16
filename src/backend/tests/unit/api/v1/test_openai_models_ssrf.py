"""SSRF regressions for OpenAI-compatible live model discovery."""

import os
import socket
from contextlib import contextmanager
from unittest import mock

import httpcore
import pytest
from fastapi import status
from httpx import AsyncClient

PUBLIC_BASE_URL = "http://models.example:8080/v1"
PUBLIC_IP = "93.184.216.34"
INTERNAL_MODEL = "instance-credential-secret"


def _requests_response(model_name: str):
    response = mock.MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"data": [{"id": model_name}]}
    return response


def _http_response(*, status_code: int = 200, body: bytes = b"", location: str | None = None):
    reason = "OK" if status_code == 200 else "Found"
    headers = [
        f"HTTP/1.1 {status_code} {reason}\r\n".encode(),
        f"Content-Length: {len(body)}\r\n".encode(),
    ]
    if location is not None:
        headers.append(f"Location: {location}\r\n".encode())
    headers.extend([b"Content-Type: application/json\r\n", b"\r\n", body])
    return httpcore.MockStream(headers)


def _public_dns(host, *_args, **_kwargs):
    assert host == "models.example"
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (PUBLIC_IP, 0))]


def _model_names(response) -> list[str]:
    return [
        model["model_name"]
        for provider in response.json()
        if provider["provider"] == "OpenAI"
        for model in provider["models"]
    ]


@contextmanager
def _patched_model_route(base_url: str):
    async def configured_openai(*_args, **_kwargs):
        return {"enabled_providers": ["OpenAI"], "provider_status": {"OpenAI": True}}

    async def no_enabled_models(*_args, **_kwargs):
        return {"enabled_models": {}, "enabled_models_by_type": {}}

    async def no_default_model(*_args, **_kwargs):
        return {}

    async def no_explicit_models(*_args, **_kwargs):
        return set()

    def provider_variable(_user_id, key):
        if key == "OPENAI_BASE_URL":
            return base_url
        if key == "OPENAI_API_KEY":
            return "sk-test"  # pragma: allowlist secret
        return None

    with (
        mock.patch("langflow.api.v1.models._get_enabled_providers_result", side_effect=configured_openai),
        mock.patch("langflow.api.v1.models._get_enabled_models_result", side_effect=no_enabled_models),
        mock.patch("langflow.api.v1.models.get_default_model", side_effect=no_default_model),
        mock.patch("langflow.api.v1.models._get_enabled_models", side_effect=no_explicit_models),
        mock.patch(
            "lfx.base.models.model_utils.get_provider_variable_value",
            side_effect=provider_variable,
        ),
    ):
        yield


@pytest.mark.usefixtures("active_user")
async def test_models_endpoint_blocks_direct_openai_metadata_target(client: AsyncClient, logged_in_headers):
    """A configured base URL cannot turn model discovery into a metadata read."""
    policy = {
        "LANGFLOW_SSRF_PROTECTION_ENABLED": "true",
        "LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED": "true",
        "LANGFLOW_CONNECTOR_SSRF_ALLOW_LOOPBACK": "false",
        "LANGFLOW_SSRF_ALLOWED_HOSTS": "",
    }
    with (
        mock.patch.dict(os.environ, policy),
        _patched_model_route("http://169.254.169.254/latest/meta-data"),
        mock.patch("requests.get", return_value=_requests_response(INTERNAL_MODEL)) as requests_get,
    ):
        response = await client.get(
            "api/v1/models",
            params={"provider": "OpenAI", "model_type": "llm"},
            headers=logged_in_headers,
        )

    assert response.status_code == status.HTTP_200_OK
    assert INTERNAL_MODEL not in _model_names(response)
    requests_get.assert_not_called()


@pytest.mark.usefixtures("active_user")
async def test_models_endpoint_blocks_redirect_to_openai_metadata_target(client: AsyncClient, logged_in_headers):
    """Every redirect hop is checked before a connection or credential reflection."""
    connected_hosts: list[str] = []

    def connect_to_public(_self, host, port, **_kwargs):
        connected_hosts.append(host)
        assert port == 8080
        return _http_response(
            status_code=302,
            location="http://169.254.169.254/latest/meta-data/models",
        )

    policy = {
        "LANGFLOW_SSRF_PROTECTION_ENABLED": "true",
        "LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED": "true",
        "LANGFLOW_CONNECTOR_SSRF_ALLOW_LOOPBACK": "false",
        "LANGFLOW_SSRF_ALLOWED_HOSTS": "",
    }
    with (
        mock.patch.dict(os.environ, policy),
        _patched_model_route(PUBLIC_BASE_URL),
        mock.patch("socket.getaddrinfo", side_effect=_public_dns),
        mock.patch.object(httpcore.SyncBackend, "connect_tcp", connect_to_public),
        # Before the fix, requests follows the redirect and exposes this final body.
        mock.patch("requests.get", return_value=_requests_response(INTERNAL_MODEL)) as requests_get,
    ):
        response = await client.get(
            "api/v1/models",
            params={"provider": "OpenAI", "model_type": "llm"},
            headers=logged_in_headers,
        )

    assert response.status_code == status.HTTP_200_OK
    assert INTERNAL_MODEL not in _model_names(response)
    requests_get.assert_not_called()
    assert connected_hosts == [PUBLIC_IP]


@pytest.mark.usefixtures("active_user")
async def test_models_endpoint_pins_public_openai_host_and_returns_models(client: AsyncClient, logged_in_headers):
    """A legitimate custom endpoint remains usable without a second DNS lookup."""
    connected_hosts: list[str] = []
    model_name = "self-hosted-model"
    body = f'{{"data":[{{"id":"{model_name}"}}]}}'.encode()

    def connect_to_public(_self, host, port, **_kwargs):
        connected_hosts.append(host)
        assert port == 8080
        return _http_response(body=body)

    policy = {
        "LANGFLOW_SSRF_PROTECTION_ENABLED": "true",
        "LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED": "true",
        "LANGFLOW_CONNECTOR_SSRF_ALLOW_LOOPBACK": "false",
        "LANGFLOW_SSRF_ALLOWED_HOSTS": "",
    }
    with (
        mock.patch.dict(os.environ, policy),
        _patched_model_route(PUBLIC_BASE_URL),
        mock.patch("socket.getaddrinfo", side_effect=_public_dns) as getaddrinfo,
        mock.patch.object(httpcore.SyncBackend, "connect_tcp", connect_to_public),
        mock.patch("requests.get", return_value=_requests_response(model_name)) as requests_get,
    ):
        response = await client.get(
            "api/v1/models",
            params={"provider": "OpenAI", "model_type": "llm"},
            headers=logged_in_headers,
        )

    assert response.status_code == status.HTTP_200_OK
    assert _model_names(response) == [model_name]
    requests_get.assert_not_called()
    assert getaddrinfo.call_count == 1
    assert connected_hosts == [PUBLIC_IP]
