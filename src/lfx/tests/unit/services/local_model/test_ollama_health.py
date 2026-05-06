"""Tests for ollama_health — async HTTP health/version queries against an Ollama server.

Threat model covered:
  - SSRF via attacker-controlled base_url → reuse ALLOWED_BASE_URLS allowlist.
  - Slow / hung Ollama → mandatory timeout, never propagate as long-running call.
  - Network errors → coerced to False / None, never crash callers.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# ---------------------------------------------------------------------------
# is_ollama_running() — boolean health probe
# ---------------------------------------------------------------------------


class TestIsOllamaRunning:
    @pytest.mark.asyncio
    async def test_should_return_true_when_server_responds_with_200(self):
        from lfx.services.local_model.ollama_health import is_ollama_running

        response = MagicMock(spec=httpx.Response, status_code=200)
        async_client = MagicMock()
        async_client.__aenter__.return_value = async_client
        async_client.__aexit__.return_value = None
        async_client.get = AsyncMock(return_value=response)

        with patch("lfx.services.local_model.ollama_health.httpx.AsyncClient", return_value=async_client):
            result = await is_ollama_running("http://localhost:11434")

        assert result is True

    @pytest.mark.asyncio
    async def test_should_return_false_on_connect_error(self):
        from lfx.services.local_model.ollama_health import is_ollama_running

        async_client = MagicMock()
        async_client.__aenter__.return_value = async_client
        async_client.__aexit__.return_value = None
        async_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

        with patch("lfx.services.local_model.ollama_health.httpx.AsyncClient", return_value=async_client):
            result = await is_ollama_running("http://localhost:11434")

        assert result is False

    @pytest.mark.asyncio
    async def test_should_return_false_on_timeout(self):
        from lfx.services.local_model.ollama_health import is_ollama_running

        async_client = MagicMock()
        async_client.__aenter__.return_value = async_client
        async_client.__aexit__.return_value = None
        async_client.get = AsyncMock(side_effect=httpx.ReadTimeout("hung"))

        with patch("lfx.services.local_model.ollama_health.httpx.AsyncClient", return_value=async_client):
            result = await is_ollama_running("http://localhost:11434")

        assert result is False

    @pytest.mark.asyncio
    async def test_should_return_false_on_non_200_status(self):
        from lfx.services.local_model.ollama_health import is_ollama_running

        response = MagicMock(spec=httpx.Response, status_code=503)
        async_client = MagicMock()
        async_client.__aenter__.return_value = async_client
        async_client.__aexit__.return_value = None
        async_client.get = AsyncMock(return_value=response)

        with patch("lfx.services.local_model.ollama_health.httpx.AsyncClient", return_value=async_client):
            result = await is_ollama_running("http://localhost:11434")

        assert result is False

    @pytest.mark.asyncio
    async def test_should_pass_explicit_timeout_to_httpx(self):
        # Why: relying on httpx defaults is brittle (changes between versions). Pin
        # a small explicit timeout here so a slow Ollama cannot stall startup.
        from lfx.services.local_model.ollama_health import is_ollama_running

        response = MagicMock(spec=httpx.Response, status_code=200)
        async_client = MagicMock()
        async_client.__aenter__.return_value = async_client
        async_client.__aexit__.return_value = None
        async_client.get = AsyncMock(return_value=response)

        with patch(
            "lfx.services.local_model.ollama_health.httpx.AsyncClient",
            return_value=async_client,
        ) as mock_client_cls:
            await is_ollama_running("http://localhost:11434", timeout_s=1.5)

        kwargs = mock_client_cls.call_args.kwargs
        assert "timeout" in kwargs
        # httpx accepts a number or httpx.Timeout — either should encode 1.5s.
        timeout = kwargs["timeout"]
        if isinstance(timeout, httpx.Timeout):
            assert timeout.read == 1.5
        else:
            assert timeout == 1.5


# ---------------------------------------------------------------------------
# SSRF guard — base_url whitelist
# ---------------------------------------------------------------------------


class TestSsrfGuard:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "malicious_url",
        [
            "http://evil.com:11434",
            "http://169.254.169.254/latest/meta-data/",
            "http://192.168.1.1:11434",
            "https://attacker.example.com",
            "file:///etc/passwd",
        ],
    )
    async def test_is_ollama_running_should_reject_non_allowlisted_url(self, malicious_url):
        from lfx.base.models.langflow_local_model import UnsafeBaseUrlError
        from lfx.services.local_model.ollama_health import is_ollama_running

        with pytest.raises(UnsafeBaseUrlError):
            await is_ollama_running(malicious_url)

    @pytest.mark.asyncio
    async def test_ollama_version_should_reject_non_allowlisted_url(self):
        from lfx.base.models.langflow_local_model import UnsafeBaseUrlError
        from lfx.services.local_model.ollama_health import ollama_version

        with pytest.raises(UnsafeBaseUrlError):
            await ollama_version("http://evil.com:11434")


# ---------------------------------------------------------------------------
# ollama_version() — returns version string or None
# ---------------------------------------------------------------------------


class TestOllamaVersion:
    @pytest.mark.asyncio
    async def test_should_return_version_string_on_success(self):
        from lfx.services.local_model.ollama_health import ollama_version

        response = MagicMock(spec=httpx.Response, status_code=200)
        response.json = MagicMock(return_value={"version": "0.5.7"})
        async_client = MagicMock()
        async_client.__aenter__.return_value = async_client
        async_client.__aexit__.return_value = None
        async_client.get = AsyncMock(return_value=response)

        with patch("lfx.services.local_model.ollama_health.httpx.AsyncClient", return_value=async_client):
            version = await ollama_version("http://localhost:11434")

        assert version == "0.5.7"

    @pytest.mark.asyncio
    async def test_should_return_none_on_network_failure(self):
        from lfx.services.local_model.ollama_health import ollama_version

        async_client = MagicMock()
        async_client.__aenter__.return_value = async_client
        async_client.__aexit__.return_value = None
        async_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

        with patch("lfx.services.local_model.ollama_health.httpx.AsyncClient", return_value=async_client):
            version = await ollama_version("http://localhost:11434")

        assert version is None

    @pytest.mark.asyncio
    async def test_should_return_none_when_response_lacks_version_field(self):
        # Why: a future Ollama version might rename the field, or a non-Ollama server
        # could be running on 11434. Returning None instead of crashing keeps callers
        # robust.
        from lfx.services.local_model.ollama_health import ollama_version

        response = MagicMock(spec=httpx.Response, status_code=200)
        response.json = MagicMock(return_value={"unexpected": "shape"})
        async_client = MagicMock()
        async_client.__aenter__.return_value = async_client
        async_client.__aexit__.return_value = None
        async_client.get = AsyncMock(return_value=response)

        with patch("lfx.services.local_model.ollama_health.httpx.AsyncClient", return_value=async_client):
            version = await ollama_version("http://localhost:11434")

        assert version is None
