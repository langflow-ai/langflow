"""Unit tests for the Ollama live-fetch path in ``model_utils``.

Covers the two fixes for issue #13137:
  - parallel fan-out (``asyncio.gather``) over per-model ``POST /api/show``
    calls and tolerance of a single model's failure;
  - in-process cache keyed by ``(base_url, capability)`` with a short TTL.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


def _build_async_client(*, tags_payload: dict, show_results: dict) -> AsyncMock:
    """Build an ``httpx.AsyncClient`` mock with deterministic /tags and /show.

    ``show_results`` maps model name -> either a dict payload (success) or an
    Exception instance (raised when /api/show is called for that model).
    """
    tags_response = MagicMock()
    tags_response.raise_for_status.return_value = None
    tags_response.json.return_value = tags_payload

    async def _get(url: str):  # noqa: ARG001 — signature for compatibility
        return tags_response

    async def _post(url: str, json: dict):  # noqa: ARG001
        model_name = json.get("model")
        result = show_results.get(model_name)
        if isinstance(result, Exception):
            raise result
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = result or {}
        return response

    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = False
    client.get = AsyncMock(side_effect=_get)
    client.post = AsyncMock(side_effect=_post)
    return client


@pytest.fixture(autouse=True)
def _clear_ollama_cache():
    """Reset the in-process Ollama model-list cache between tests."""
    from lfx.base.models.model_utils import _ollama_cache_clear

    _ollama_cache_clear()
    yield
    _ollama_cache_clear()


@pytest.mark.asyncio
async def test_get_ollama_models_returns_only_matching_capability():
    from lfx.base.models import model_utils

    tags = {"models": [{"name": "llama3"}, {"name": "mxbai-embed-large"}, {"name": "qwen2"}]}
    show_results = {
        "llama3": {"capabilities": ["completion"]},
        "mxbai-embed-large": {"capabilities": ["embedding"]},
        "qwen2": {"capabilities": ["completion", "tools"]},
    }
    client = _build_async_client(tags_payload=tags, show_results=show_results)

    with patch.object(model_utils.httpx, "AsyncClient", return_value=client):
        result = await model_utils.get_ollama_models(
            base_url_value="http://localhost:11434",
            desired_capability="completion",
            json_models_key="models",
            json_name_key="name",
            json_capabilities_key="capabilities",
        )

    assert result == ["llama3", "qwen2"]


@pytest.mark.asyncio
async def test_get_ollama_models_runs_show_requests_in_parallel():
    """All ``POST /api/show`` calls are awaited together via asyncio.gather.

    Walltime ≈ max(per-request latency), not sum. We pin this by sending each
    request through an asyncio.Event that has to be released collectively
    after every show call has been issued.
    """
    import asyncio

    from lfx.base.models import model_utils

    tags = {"models": [{"name": f"m{i}"} for i in range(8)]}
    started = 0
    started_event = asyncio.Event()

    async def fake_post(url: str, json: dict):  # noqa: ARG001
        nonlocal started
        started += 1
        if started == len(tags["models"]):
            started_event.set()
        # Block until every call has started; if calls were sequential this
        # would deadlock because the first call would wait forever.
        await asyncio.wait_for(started_event.wait(), timeout=1.0)
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"capabilities": ["completion"]}
        return response

    tags_response = MagicMock()
    tags_response.raise_for_status.return_value = None
    tags_response.json.return_value = tags

    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = False
    client.get = AsyncMock(return_value=tags_response)
    client.post = AsyncMock(side_effect=fake_post)

    with patch.object(model_utils.httpx, "AsyncClient", return_value=client):
        result = await model_utils.get_ollama_models(
            base_url_value="http://localhost:11434",
            desired_capability="completion",
            json_models_key="models",
            json_name_key="name",
            json_capabilities_key="capabilities",
        )

    assert result == sorted(f"m{i}" for i in range(8))
    assert client.post.await_count == 8


@pytest.mark.asyncio
async def test_get_ollama_models_tolerates_single_show_failure():
    """One bad model must not poison the whole catalog response."""
    from lfx.base.models import model_utils

    tags = {"models": [{"name": "llama3"}, {"name": "broken"}, {"name": "qwen2"}]}
    show_results = {
        "llama3": {"capabilities": ["completion"]},
        "broken": httpx.RequestError("simulated 500 from /api/show"),
        "qwen2": {"capabilities": ["completion"]},
    }
    client = _build_async_client(tags_payload=tags, show_results=show_results)

    with patch.object(model_utils.httpx, "AsyncClient", return_value=client):
        result = await model_utils.get_ollama_models(
            base_url_value="http://localhost:11434",
            desired_capability="completion",
            json_models_key="models",
            json_name_key="name",
            json_capabilities_key="capabilities",
        )

    assert result == ["llama3", "qwen2"]


@pytest.mark.asyncio
async def test_get_ollama_models_caches_result_for_ttl_window():
    """A second call within the TTL must not hit Ollama again."""
    from lfx.base.models import model_utils

    tags = {"models": [{"name": "llama3"}]}
    show = {"llama3": {"capabilities": ["completion"]}}
    client = _build_async_client(tags_payload=tags, show_results=show)

    with patch.object(model_utils.httpx, "AsyncClient", return_value=client):
        first = await model_utils.get_ollama_models(
            base_url_value="http://localhost:11434",
            desired_capability="completion",
            json_models_key="models",
            json_name_key="name",
            json_capabilities_key="capabilities",
        )
        second = await model_utils.get_ollama_models(
            base_url_value="http://localhost:11434",
            desired_capability="completion",
            json_models_key="models",
            json_name_key="name",
            json_capabilities_key="capabilities",
        )

    assert first == ["llama3"]
    assert second == ["llama3"]
    # One /api/tags + one /api/show on the first call; the second call must
    # return entirely from the cache.
    assert client.get.await_count == 1
    assert client.post.await_count == 1


@pytest.mark.asyncio
async def test_get_ollama_models_cache_keyed_by_base_url_and_capability():
    """Different base URLs or capability filters must not collide."""
    from lfx.base.models import model_utils

    tags = {"models": [{"name": "llama3"}, {"name": "mxbai-embed-large"}]}
    show = {
        "llama3": {"capabilities": ["completion"]},
        "mxbai-embed-large": {"capabilities": ["embedding"]},
    }
    client = _build_async_client(tags_payload=tags, show_results=show)

    with patch.object(model_utils.httpx, "AsyncClient", return_value=client):
        llms = await model_utils.get_ollama_models(
            base_url_value="http://localhost:11434",
            desired_capability="completion",
            json_models_key="models",
            json_name_key="name",
            json_capabilities_key="capabilities",
        )
        embs = await model_utils.get_ollama_models(
            base_url_value="http://localhost:11434",
            desired_capability="embedding",
            json_models_key="models",
            json_name_key="name",
            json_capabilities_key="capabilities",
        )
        other_base = await model_utils.get_ollama_models(
            base_url_value="http://other-host:11434",
            desired_capability="completion",
            json_models_key="models",
            json_name_key="name",
            json_capabilities_key="capabilities",
        )

    assert llms == ["llama3"]
    assert embs == ["mxbai-embed-large"]
    assert other_base == ["llama3"]
    # 3 distinct cache entries → 3 /api/tags round-trips and 6 /api/show
    # round-trips (2 per fetch). If the cache key collided we'd see fewer.
    assert client.get.await_count == 3
    assert client.post.await_count == 6


@pytest.mark.asyncio
async def test_get_ollama_models_refetches_after_ttl_expires():
    """Once the TTL passes, a follow-up call hits Ollama again."""
    from lfx.base.models import model_utils

    tags = {"models": [{"name": "llama3"}]}
    show = {"llama3": {"capabilities": ["completion"]}}
    client = _build_async_client(tags_payload=tags, show_results=show)

    fake_now = 0.0

    def monotonic_stub() -> float:
        return fake_now

    with (
        patch.object(model_utils.time, "monotonic", side_effect=monotonic_stub),
        patch.object(model_utils.httpx, "AsyncClient", return_value=client),
    ):
        first = await model_utils.get_ollama_models(
            base_url_value="http://localhost:11434",
            desired_capability="completion",
            json_models_key="models",
            json_name_key="name",
            json_capabilities_key="capabilities",
        )
        # Advance past the TTL window.
        fake_now = model_utils._OLLAMA_MODEL_LIST_TTL_SECONDS + 1
        second = await model_utils.get_ollama_models(
            base_url_value="http://localhost:11434",
            desired_capability="completion",
            json_models_key="models",
            json_name_key="name",
            json_capabilities_key="capabilities",
        )

    assert first == ["llama3"]
    assert second == ["llama3"]
    # Second call missed the cache → two /api/tags fetches total.
    assert client.get.await_count == 2
