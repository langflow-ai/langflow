import json
import socket
import unittest
from unittest.mock import patch

import httpx
import pytest
from lfx_arcmira.client import ArcmiraReadError, read
from pydantic import SecretStr


class ReadTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.network = patch.object(socket.socket, "connect", side_effect=AssertionError("Unexpected real network"))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.calls = []
        self.client_type = httpx.AsyncClient

    def transport(self, status=200, body=None, headers=None, failure=None, content=None):
        def handler(request):
            self.calls.append(request)
            if failure:
                msg = "synthetic-secret"
                raise failure(msg, request=request)
            return (
                httpx.Response(status, json=body, headers=headers)
                if content is None
                else httpx.Response(status, content=content)
            )

        def factory(**kwargs):
            assert kwargs == {"timeout": 30, "follow_redirects": False}
            return self.client_type(transport=httpx.MockTransport(handler), **kwargs)

        return patch("lfx_arcmira.client.httpx.AsyncClient", side_effect=factory)

    async def test_full_envelope_and_filters(self):
        body = {
            "chunks": [{"text": "passage", "url": "https://youtube.com/watch?v=x&t=4", "start_seconds": 4}],
            "coverage": {"note": "partial"},
            "access": {"plan": "free"},
            "future_metadata": [1],
        }
        params = {
            "q": "climate",
            "limit": 5,
            "source": "arcmira_premium",
            "channel_ids": "UC1",
            "entity_ids": "ent_1",
            "about": "ent_2",
            "by": "ent_3",
            "kind": "sponsored,organic",
            "after": "2026-01-01",
            "before": "2026-02-01",
        }
        with self.transport(body=body):
            assert await read(SecretStr("synthetic-secret"), "search", params) == body
        assert dict(self.calls[0].url.params) == {k: str(v) for k, v in params.items()}
        assert self.calls[0].headers["authorization"] == "Bearer synthetic-secret"
        assert len(self.calls) == 1

    async def test_empty_results_preserve_coverage(self):
        body = {"chunks": [], "coverage": {"complete": False, "note": "No labeled speakers"}}
        with self.transport(body=body):
            assert await read("synthetic-secret", "search", {"q": "test"}) == body

    async def test_ambiguous_resolution_preserved(self):
        body = {
            "candidates": [{"id": "ent_1"}, {"id": "ent_2"}],
            "needs_clarification": True,
            "suggested": None,
            "reason": "ambiguous",
        }
        with self.transport(body=body):
            assert (
                await read(
                    "synthetic-secret",
                    "entities/resolve",
                    {"q": "John", "context": "a podcast", "type": "person", "limit": 8},
                )
                == body
            )
        assert self.calls[0].url.params["context"] == "a podcast"

    async def test_refusals_preserve_body_without_retry_or_fallback(self):
        for status in (400, 401, 403, 429, 500):
            with (
                self.subTest(status=status),
                self.transport(
                    status,
                    {"error": "filter_requires_paid", "access": {"required_plan": "pro"}},
                    {"Retry-After": "60", "X-Request-Id": "fixture-id"},
                ),
            ):
                with pytest.raises(ArcmiraReadError) as got:
                    await read("synthetic-secret", "search", {"q": "test", "source": "arcmira_premium"})
                assert got.value.status == status
                assert got.value.body["access"] == {"required_plan": "pro"}
                assert got.value.headers == {"retry-after": "60", "x-request-id": "fixture-id"}
        assert len(self.calls) == 5
        assert all(c.url.params["source"] == "arcmira_premium" for c in self.calls)

    async def test_error_echo_redacts_secret(self):
        with (
            self.transport(
                403,
                {"error": "synthetic-secret", "nested": ["Bearer synthetic-secret"]},
                {"x-request-id": "synthetic-secret"},
            ),
            pytest.raises(ArcmiraReadError) as got,
        ):
            await read("synthetic-secret", "search", {"q": "test"})
        assert "synthetic-secret" not in str(got.value)
        assert "synthetic-secret" not in json.dumps(got.value.body)
        assert got.value.headers["x-request-id"] == "[REDACTED]"

    async def test_json_escaped_error_echo_redacts_secret(self):
        key = 'synthetic-"secret'
        with self.transport(403, {key: [key]}), pytest.raises(ArcmiraReadError) as got:
            await read(key, "search", {"q": "test"})
        assert got.value.body == {"[REDACTED]": ["[REDACTED]"]}

    async def test_timeout_no_retry_or_secret(self):
        with self.transport(failure=httpx.ReadTimeout), pytest.raises(RuntimeError, match="no automatic retry") as got:
            await read("synthetic-secret", "search", {"q": "test"})
        assert "synthetic-secret" not in str(got.value)
        assert len(self.calls) == 1

    async def test_redirect_is_not_followed(self):
        with (
            self.transport(302, {"redirect": True}, {"location": "https://other.invalid"}),
            pytest.raises(ArcmiraReadError),
        ):
            await read("synthetic-secret", "search", {"q": "test"})
        assert len(self.calls) == 1

    async def test_non_json_and_malformed_success(self):
        with self.transport(content=b"not json"), pytest.raises(RuntimeError, match="non-JSON"):
            await read("synthetic-secret", "search", {"q": "test"})
        for body in ([], {}, {"chunks": "bad"}):
            with self.transport(body=body), pytest.raises(RuntimeError, match="unexpected response"):
                await read("synthetic-secret", "search", {"q": "test"})

    async def test_invalid_inputs_do_not_request(self):
        for key, path, params in [
            ("", "search", {"q": "ok"}),
            ("key", "other", {"q": "ok"}),
            ("key", "search", {"q": "x"}),
            ("key", "search", {"q": "ok", "limit": True}),
            ("key", "search", {"q": "ok", "limit": 21}),
            ("key", "entities/resolve", {"q": "ok", "limit": 16}),
        ]:
            with self.subTest(params=params), pytest.raises(ValueError, match=r"required|Unsupported|at least|integer"):
                await read(key, path, params)
        assert self.calls == []

    async def test_omits_blank_optional_fields(self):
        with self.transport(body={"candidates": []}):
            await read("synthetic-secret", "entities/resolve", {"q": "test", "context": "", "type": None, "limit": 8})
        assert dict(self.calls[0].url.params) == {"q": "test", "limit": "8"}


if __name__ == "__main__":
    unittest.main()
