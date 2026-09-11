from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from lfx_bundles.context._client import CONTEXT_API_BASE_URL, request_context

TEST_API_KEY = "test-context-api-key"


@pytest.mark.unit
async def test_request_context_authenticates_against_production_api() -> None:
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"results": []}
    client = AsyncMock()
    client.request.return_value = response
    client_context = AsyncMock()
    client_context.__aenter__.return_value = client

    with patch("lfx_bundles.context._client.httpx.AsyncClient", return_value=client_context) as client_class:
        result = await request_context("POST", "/web/search", TEST_API_KEY, json={"query": "Langflow"})

    assert result == {"results": []}
    client_class.assert_called_once_with(base_url=CONTEXT_API_BASE_URL, timeout=120)
    client.request.assert_awaited_once_with(
        "POST",
        "/web/search",
        headers={"Authorization": f"Bearer {TEST_API_KEY}", "Accept": "application/json"},
        params=None,
        json={"query": "Langflow"},
    )


@pytest.mark.unit
async def test_request_context_surfaces_api_error_message() -> None:
    request = httpx.Request("POST", f"{CONTEXT_API_BASE_URL}/web/search")
    response = httpx.Response(401, request=request, json={"message": "Invalid API key"})
    client = AsyncMock()
    client.request.return_value = response
    client_context = AsyncMock()
    client_context.__aenter__.return_value = client

    with (
        patch("lfx_bundles.context._client.httpx.AsyncClient", return_value=client_context),
        pytest.raises(ValueError, match="HTTP 401: Invalid API key"),
    ):
        await request_context("POST", "/web/search", TEST_API_KEY, json={"query": "Langflow"})


@pytest.mark.unit
async def test_request_context_rejects_missing_api_key() -> None:
    with pytest.raises(ValueError, match="API key is required"):
        await request_context("GET", "/brand/retrieve", "")
