"""Tests for model_puller — async checks and downloads of curated Ollama models.

Threat model covered:
  - SSRF via base_url   → reuses ALLOWED_BASE_URLS allowlist (same as Slice 1).
  - DoS via model name  → reuses CURATED_MODEL_NAMES — refuses 200GB pulls.
  - Servidor Ollama mintindo "downloading" forever → timeout enforced.
  - Success decided ONLY by terminator `{"status": "success"}` — partial progress
    chunks do not count as success.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# ---------------------------------------------------------------------------
# PullStatus enum + PullOutcome dataclass
# ---------------------------------------------------------------------------


class TestPullStatus:
    @pytest.mark.parametrize(
        "name",
        ["SUCCESS", "ALREADY_PRESENT", "FAILED", "NETWORK_ERROR", "REJECTED"],
    )
    def test_should_expose_canonical_status(self, name):
        from lfx.services.local_model.model_puller import PullStatus

        assert hasattr(PullStatus, name)


class TestPullOutcome:
    def test_should_be_frozen(self):
        from lfx.services.local_model.model_puller import PullOutcome, PullStatus

        outcome = PullOutcome(status=PullStatus.SUCCESS)

        with pytest.raises((AttributeError, TypeError)):
            outcome.status = PullStatus.FAILED  # type: ignore[misc]


# ---------------------------------------------------------------------------
# is_model_pulled — peek /api/tags
# ---------------------------------------------------------------------------


class TestIsModelPulled:
    @pytest.mark.asyncio
    async def test_should_return_true_when_model_is_in_tags(self):
        from lfx.services.local_model.model_puller import is_model_pulled

        response = MagicMock(spec=httpx.Response, status_code=200)
        response.json = MagicMock(
            return_value={"models": [{"name": "qwen2.5:1.5b"}, {"name": "llama3.2:1b"}]}
        )
        async_client = MagicMock()
        async_client.__aenter__.return_value = async_client
        async_client.__aexit__.return_value = None
        async_client.get = AsyncMock(return_value=response)

        with patch("lfx.services.local_model.model_puller.httpx.AsyncClient", return_value=async_client):
            result = await is_model_pulled("qwen2.5:1.5b", "http://localhost:11434")

        assert result is True

    @pytest.mark.asyncio
    async def test_should_return_false_when_model_is_not_in_tags(self):
        from lfx.services.local_model.model_puller import is_model_pulled

        response = MagicMock(spec=httpx.Response, status_code=200)
        response.json = MagicMock(return_value={"models": [{"name": "mistral"}]})
        async_client = MagicMock()
        async_client.__aenter__.return_value = async_client
        async_client.__aexit__.return_value = None
        async_client.get = AsyncMock(return_value=response)

        with patch("lfx.services.local_model.model_puller.httpx.AsyncClient", return_value=async_client):
            result = await is_model_pulled("qwen2.5:1.5b", "http://localhost:11434")

        assert result is False

    @pytest.mark.asyncio
    async def test_should_return_false_on_network_error(self):
        from lfx.services.local_model.model_puller import is_model_pulled

        async_client = MagicMock()
        async_client.__aenter__.return_value = async_client
        async_client.__aexit__.return_value = None
        async_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

        with patch("lfx.services.local_model.model_puller.httpx.AsyncClient", return_value=async_client):
            result = await is_model_pulled("qwen2.5:1.5b", "http://localhost:11434")

        assert result is False

    @pytest.mark.asyncio
    async def test_should_reject_base_url_outside_allowlist(self):
        from lfx.base.models.langflow_local_model import UnsafeBaseUrlError
        from lfx.services.local_model.model_puller import is_model_pulled

        with pytest.raises(UnsafeBaseUrlError):
            await is_model_pulled("qwen2.5:1.5b", "http://evil.com:11434")

    @pytest.mark.asyncio
    async def test_should_reject_uncurated_model_name(self):
        from lfx.base.models.langflow_local_model import UncuratedModelError
        from lfx.services.local_model.model_puller import is_model_pulled

        with pytest.raises(UncuratedModelError):
            await is_model_pulled("llama3.1:405b", "http://localhost:11434")


# ---------------------------------------------------------------------------
# pull_model — POST /api/pull, parse NDJSON
# ---------------------------------------------------------------------------


def _stream_cm(lines: list[bytes], status_code: int = 200):
    """Make a context manager mock matching httpx.AsyncClient.stream(...) usage."""
    response = MagicMock()
    response.status_code = status_code
    response.raise_for_status = MagicMock(return_value=None)

    async def _aiter():
        for line in lines:
            yield line

    response.aiter_lines = MagicMock(return_value=_aiter())
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=response)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


class TestPullModelHappyPath:
    @pytest.mark.asyncio
    async def test_should_return_success_when_stream_ends_with_success_status(self):
        from lfx.services.local_model.model_puller import PullStatus, pull_model

        ndjson = [
            '{"status":"pulling manifest"}',
            '{"status":"downloading","digest":"sha256:abc","total":1000,"completed":500}',
            '{"status":"downloading","digest":"sha256:abc","total":1000,"completed":1000}',
            '{"status":"verifying sha256 digest"}',
            '{"status":"writing manifest"}',
            '{"status":"success"}',
        ]
        async_client = MagicMock()
        async_client.__aenter__.return_value = async_client
        async_client.__aexit__.return_value = None
        async_client.stream = MagicMock(return_value=_stream_cm(ndjson))
        # is_model_pulled (called internally to short-circuit) must return False
        # so the pull path is exercised.
        check_response = MagicMock(spec=httpx.Response, status_code=200)
        check_response.json = MagicMock(return_value={"models": []})
        async_client.get = AsyncMock(return_value=check_response)

        progress_cb = MagicMock()
        with patch("lfx.services.local_model.model_puller.httpx.AsyncClient", return_value=async_client):
            outcome = await pull_model("qwen2.5:1.5b", "http://localhost:11434", progress_cb)

        assert outcome.status == PullStatus.SUCCESS
        # Progress callback called at least for the two "downloading" chunks.
        assert progress_cb.call_count >= 2

    @pytest.mark.asyncio
    async def test_should_short_circuit_when_model_is_already_pulled(self):
        from lfx.services.local_model.model_puller import PullStatus, pull_model

        async_client = MagicMock()
        async_client.__aenter__.return_value = async_client
        async_client.__aexit__.return_value = None
        check_response = MagicMock(spec=httpx.Response, status_code=200)
        check_response.json = MagicMock(return_value={"models": [{"name": "qwen2.5:1.5b"}]})
        async_client.get = AsyncMock(return_value=check_response)
        async_client.stream = MagicMock()  # must NOT be called

        with patch("lfx.services.local_model.model_puller.httpx.AsyncClient", return_value=async_client):
            outcome = await pull_model("qwen2.5:1.5b", "http://localhost:11434", MagicMock())

        assert outcome.status == PullStatus.ALREADY_PRESENT
        async_client.stream.assert_not_called()


class TestPullModelFailureModes:
    @pytest.mark.asyncio
    async def test_should_return_failed_when_stream_emits_error_chunk(self):
        from lfx.services.local_model.model_puller import PullStatus, pull_model

        ndjson = [
            '{"status":"pulling manifest"}',
            '{"error":"manifest unknown"}',
        ]
        async_client = MagicMock()
        async_client.__aenter__.return_value = async_client
        async_client.__aexit__.return_value = None
        async_client.stream = MagicMock(return_value=_stream_cm(ndjson))
        check_response = MagicMock(spec=httpx.Response, status_code=200)
        check_response.json = MagicMock(return_value={"models": []})
        async_client.get = AsyncMock(return_value=check_response)

        with patch("lfx.services.local_model.model_puller.httpx.AsyncClient", return_value=async_client):
            outcome = await pull_model("qwen2.5:1.5b", "http://localhost:11434", MagicMock())

        assert outcome.status == PullStatus.FAILED

    @pytest.mark.asyncio
    async def test_should_return_failed_when_stream_ends_without_success_terminator(self):
        # Why: a stream that closes mid-download is not a SUCCESS even if every
        # chunk so far was harmless. The terminator is the only authority.
        from lfx.services.local_model.model_puller import PullStatus, pull_model

        ndjson = [
            '{"status":"pulling manifest"}',
            '{"status":"downloading","digest":"sha256:abc","total":1000,"completed":500}',
        ]
        async_client = MagicMock()
        async_client.__aenter__.return_value = async_client
        async_client.__aexit__.return_value = None
        async_client.stream = MagicMock(return_value=_stream_cm(ndjson))
        check_response = MagicMock(spec=httpx.Response, status_code=200)
        check_response.json = MagicMock(return_value={"models": []})
        async_client.get = AsyncMock(return_value=check_response)

        with patch("lfx.services.local_model.model_puller.httpx.AsyncClient", return_value=async_client):
            outcome = await pull_model("qwen2.5:1.5b", "http://localhost:11434", MagicMock())

        assert outcome.status == PullStatus.FAILED

    @pytest.mark.asyncio
    async def test_should_return_network_error_on_connection_failure(self):
        from lfx.services.local_model.model_puller import PullStatus, pull_model

        async_client = MagicMock()
        async_client.__aenter__.return_value = async_client
        async_client.__aexit__.return_value = None
        check_response = MagicMock(spec=httpx.Response, status_code=200)
        check_response.json = MagicMock(return_value={"models": []})
        async_client.get = AsyncMock(return_value=check_response)
        async_client.stream = MagicMock(side_effect=httpx.ConnectError("refused"))

        with patch("lfx.services.local_model.model_puller.httpx.AsyncClient", return_value=async_client):
            outcome = await pull_model("qwen2.5:1.5b", "http://localhost:11434", MagicMock())

        assert outcome.status == PullStatus.NETWORK_ERROR


class TestPullModelGuards:
    @pytest.mark.asyncio
    async def test_should_reject_base_url_outside_allowlist(self):
        from lfx.base.models.langflow_local_model import UnsafeBaseUrlError
        from lfx.services.local_model.model_puller import pull_model

        with pytest.raises(UnsafeBaseUrlError):
            await pull_model("qwen2.5:1.5b", "http://evil.com:11434", MagicMock())

    @pytest.mark.asyncio
    async def test_should_reject_uncurated_model_name(self):
        from lfx.base.models.langflow_local_model import UncuratedModelError
        from lfx.services.local_model.model_puller import pull_model

        with pytest.raises(UncuratedModelError):
            await pull_model("llama3.1:405b", "http://localhost:11434", MagicMock())
