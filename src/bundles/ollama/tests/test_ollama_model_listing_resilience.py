"""One unreachable Ollama model must not empty the whole model dropdown.

``get_model`` / ``get_models`` enumerate every model from ``/api/tags`` and call
``/api/show`` on each to read its capabilities. Both called ``raise_for_status()``
inside that loop, so the FIRST model the server refuses aborted the enumeration and
the picker came back empty.

Reproduced on a real Ollama 0.x install: a cloud model the daemon is not signed in
for answers ``410 Gone`` on ``/api/show`` while every local model answers ``200``.
With ``glm-5:cloud`` first in ``/api/tags``, the locally installed
``nomic-embed-text:latest`` was never reached and the editor showed
"Error while updating the Component".

The leaked message is a second defect: ``httpx.HTTPStatusError`` is NOT a subclass of
``httpx.RequestError``, so it escaped the ``except`` that was meant to translate
transport failures into "Could not get model names from Ollama." and the raw httpx
text reached the UI instead.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from lfx_ollama.components.ollama.ollama import ChatOllamaComponent
from lfx_ollama.components.ollama.ollama_embeddings import OllamaEmbeddingsComponent

BASE_URL = "http://localhost:11434"
MODULE_EMBEDDINGS = "lfx_ollama.components.ollama.ollama_embeddings"
MODULE_CHAT = "lfx_ollama.components.ollama.ollama"

# Verbatim from the live daemon: the cloud model is listed but cannot be inspected.
TAGS = {
    "models": [
        {"name": "glm-5:cloud"},
        {"name": "nomic-embed-text:latest"},
        {"name": "llama3.2:latest"},
    ]
}
CAPABILITIES = {
    "nomic-embed-text:latest": ["embedding"],
    "llama3.2:latest": ["completion", "tools"],
}


def _response(status: int, payload: dict | None = None) -> httpx.Response:
    request = httpx.Request("POST", f"{BASE_URL}/api/show")
    return httpx.Response(status_code=status, json=payload or {}, request=request)


def _show(url, json, headers=None, **_kwargs):  # noqa: ARG001
    model = json["model"]
    if model == "glm-5:cloud":
        return _response(410, {"error": "model not found"})
    return _response(200, {"capabilities": CAPABILITIES[model]})


def _tags(*_args, **_kwargs) -> httpx.Response:
    request = httpx.Request("GET", f"{BASE_URL}/api/tags")
    return httpx.Response(status_code=200, json=TAGS, request=request)


@pytest.mark.asyncio
async def test_embeddings_listing_skips_a_model_it_cannot_inspect():
    component = OllamaEmbeddingsComponent()

    with (
        patch(f"{MODULE_EMBEDDINGS}.ssrf_safe_async_get", new=AsyncMock(side_effect=_tags)),
        patch(f"{MODULE_EMBEDDINGS}.ssrf_safe_async_post", new=AsyncMock(side_effect=_show)),
    ):
        models = await component.get_model(BASE_URL)

    assert models == ["nomic-embed-text:latest"], "one unreachable model emptied the dropdown"


@pytest.mark.asyncio
async def test_chat_listing_skips_a_model_it_cannot_inspect():
    component = ChatOllamaComponent()

    with (
        patch(f"{MODULE_CHAT}.ssrf_safe_async_get", new=AsyncMock(side_effect=_tags)),
        patch(f"{MODULE_CHAT}.ssrf_safe_async_post", new=AsyncMock(side_effect=_show)),
    ):
        models = await component.get_models(BASE_URL)

    assert "llama3.2:latest" in models
    assert "glm-5:cloud" not in models


@pytest.mark.asyncio
async def test_a_failing_tags_request_still_reports_the_friendly_error():
    """The daemon itself being unreachable is a different failure and must stay loud."""
    component = OllamaEmbeddingsComponent()

    def _dead_tags(*_args, **_kwargs):
        request = httpx.Request("GET", f"{BASE_URL}/api/tags")
        return httpx.Response(status_code=500, json={}, request=request)

    with (
        patch(f"{MODULE_EMBEDDINGS}.ssrf_safe_async_get", new=AsyncMock(side_effect=_dead_tags)),
        pytest.raises(ValueError, match="Could not get model names from Ollama"),
    ):
        await component.get_model(BASE_URL)
