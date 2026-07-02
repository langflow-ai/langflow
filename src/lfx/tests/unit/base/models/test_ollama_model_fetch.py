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
    """Different base URLs or capability filters must not collide.

    The list cache is keyed by ``(base_url, capability)`` so each distinct
    fetch still re-resolves its own ``/api/tags``. The *capability* cache,
    however, is keyed by ``(base_url, model_name)`` and outlives a single
    fetch, so the second capability filter on the same base URL reuses the
    first fetch's ``/api/show`` probes instead of fanning out again.
    """
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
    # 3 distinct list-cache entries → 3 /api/tags round-trips. Only 4
    # /api/show round-trips though, not 6: the embedding fetch on
    # localhost reuses the 2 capability probes from the completion fetch,
    # while other-host probes its 2 models fresh.
    assert client.get.await_count == 3
    assert client.post.await_count == 4


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
    # Second call missed the short list cache → a second /api/tags fetch.
    assert client.get.await_count == 2
    # …but the per-model capability cache has a much longer TTL, so the
    # re-listed model is NOT re-probed: still only one /api/show overall.
    assert client.post.await_count == 1


@pytest.mark.asyncio
async def test_get_ollama_models_does_not_cache_empty_capabilities():
    """A 200 /api/show with no capabilities is not cached, so it is re-probed.

    Caching an empty/absent capability array would hide a model from the
    picker for the full capability TTL if that empty response were transient
    (e.g. a model still warming up on Ollama Cloud). Leaving it uncached
    matches the error path: retried on the next catalog read.
    """
    from lfx.base.models import model_utils

    tags = {"models": [{"name": "llama3"}, {"name": "warming-up"}]}
    show = {
        "llama3": {"capabilities": ["completion"]},
        "warming-up": {},  # 200 with no capabilities key
    }
    client = _build_async_client(tags_payload=tags, show_results=show)

    fake_now = 0.0

    def monotonic_stub() -> float:
        return fake_now

    base = "http://localhost:11434"
    with (
        patch.object(model_utils.time, "monotonic", side_effect=monotonic_stub),
        patch.object(model_utils.httpx, "AsyncClient", return_value=client),
    ):
        first = await model_utils.get_ollama_models(
            base_url_value=base,
            desired_capability="completion",
            json_models_key="models",
            json_name_key="name",
            json_capabilities_key="capabilities",
        )
        # The empty response must not have been cached.
        assert (base, "warming-up") not in model_utils._ollama_capability_cache
        # The model finishes warming up and now reports a completion capability.
        show["warming-up"] = {"capabilities": ["completion"]}
        # Advance past the short list TTL so the catalog is re-listed.
        fake_now = model_utils._OLLAMA_MODEL_LIST_TTL_SECONDS + 1
        second = await model_utils.get_ollama_models(
            base_url_value=base,
            desired_capability="completion",
            json_models_key="models",
            json_name_key="name",
            json_capabilities_key="capabilities",
        )

    assert first == ["llama3"]
    # "warming-up" was re-probed (not stuck as cached-empty) and now appears.
    assert second == ["llama3", "warming-up"]
    # llama3 probed once total (cached across both reads); "warming-up" probed
    # on BOTH reads because the empty first response was never cached:
    # 1 (llama3) + 2 (warming-up) = 3 /api/show calls.
    assert client.post.await_count == 3


@pytest.mark.asyncio
async def test_capability_cache_prunes_departed_models():
    """Capability entries for models no longer in the catalog are evicted.

    Without pruning the per-model cache would keep one entry per distinct
    model ever seen for the process lifetime; on Ollama Cloud's large,
    evolving catalog that is unnecessary retention. Pruning on each fresh
    catalog read bounds it to the live catalog.
    """
    from lfx.base.models import model_utils

    tags = {"models": [{"name": "llama3"}, {"name": "transient"}]}
    show = {
        "llama3": {"capabilities": ["completion"]},
        "transient": {"capabilities": ["completion"]},
    }
    client = _build_async_client(tags_payload=tags, show_results=show)

    fake_now = 0.0

    def monotonic_stub() -> float:
        return fake_now

    base = "http://localhost:11434"
    with (
        patch.object(model_utils.time, "monotonic", side_effect=monotonic_stub),
        patch.object(model_utils.httpx, "AsyncClient", return_value=client),
    ):
        first = await model_utils.get_ollama_models(
            base_url_value=base,
            desired_capability="completion",
            json_models_key="models",
            json_name_key="name",
            json_capabilities_key="capabilities",
        )
        assert (base, "transient") in model_utils._ollama_capability_cache

        # "transient" drops out of the catalog; advance past the list TTL so
        # the catalog is actually re-fetched (and thus pruned).
        tags["models"] = [{"name": "llama3"}]
        fake_now = model_utils._OLLAMA_MODEL_LIST_TTL_SECONDS + 1
        second = await model_utils.get_ollama_models(
            base_url_value=base,
            desired_capability="completion",
            json_models_key="models",
            json_name_key="name",
            json_capabilities_key="capabilities",
        )

    assert first == ["llama3", "transient"]
    assert second == ["llama3"]
    # The departed model's capability entry was pruned on the second read.
    assert (base, "transient") not in model_utils._ollama_capability_cache
    # llama3's entry survives (still listed, still within the capability TTL).
    assert (base, "llama3") in model_utils._ollama_capability_cache


@pytest.mark.asyncio
async def test_llm_and_embedding_reads_share_one_show_fanout():
    """The ``model_type=None`` path must not probe the catalog twice.

    ``GET /enabled_models`` fetches both llm and embedding live models
    (``replace_with_live_models(model_type=None)``) on every refetch. Before
    the per-model capability cache that meant ``2 x (N + 1)`` upstream calls
    per read on Ollama Cloud's large public catalog — the root cause of the
    toggle slowness in issue #12399. The two reads must now share a single
    ``/api/show`` fan-out: ``N`` probes total, not ``2N``.
    """
    from lfx.base.models import model_utils

    tags = {
        "models": [
            {"name": "llama3"},
            {"name": "qwen2"},
            {"name": "mxbai-embed-large"},
            {"name": "nomic-embed-text"},
        ]
    }
    show = {
        "llama3": {"capabilities": ["completion", "tools"]},
        "qwen2": {"capabilities": ["completion"]},
        "mxbai-embed-large": {"capabilities": ["embedding"]},
        "nomic-embed-text": {"capabilities": ["embedding"]},
    }
    client = _build_async_client(tags_payload=tags, show_results=show)

    with patch.object(model_utils.httpx, "AsyncClient", return_value=client):
        llms = await model_utils.get_ollama_llm_models("http://ollama.com")
        embs = await model_utils.get_ollama_embedding_models("http://ollama.com")

    assert llms == ["llama3", "qwen2"]
    assert embs == ["mxbai-embed-large", "nomic-embed-text"]
    # 4 models probed exactly once across BOTH reads — the embedding read
    # reused every capability the llm read already fetched.
    assert client.post.await_count == len(tags["models"])
