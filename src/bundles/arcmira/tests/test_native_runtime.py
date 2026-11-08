"""Exercise installed LFX components and tool artifacts with transport fixtures."""

import socket
import unittest
from unittest.mock import patch

import httpx
import pytest
from lfx_arcmira.client import ArcmiraReadError
from lfx_arcmira.components.arcmira.resolve import ArcmiraEntityResolve
from lfx_arcmira.components.arcmira.search import ArcmiraTranscriptSearch


class NativeRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.calls = []
        self.real_client = httpx.AsyncClient
        self.guard = patch.object(socket.socket, "connect", side_effect=AssertionError("Unexpected network"))
        self.guard.start()
        self.addCleanup(self.guard.stop)

    def transport(self, body, status=200):
        def handle(request):
            self.calls.append(request)
            return httpx.Response(status, json=body, headers={"Retry-After": "60"})

        return patch(
            "lfx_arcmira.client.httpx.AsyncClient",
            side_effect=lambda **kw: self.real_client(transport=httpx.MockTransport(handle), **kw),
        )

    async def test_component_search_output(self):
        component = ArcmiraTranscriptSearch()
        component.set(api_key="synthetic-native-key", query="climate", source="arcmira_premium", limit=5, by="person_1")
        body = {
            "chunks": [{"text": "example", "start_seconds": 17}],
            "coverage": {"complete": False},
            "future_metadata": ["preserved"],
        }
        with self.transport(body):
            output = await component.search_transcripts()
        assert output.data == body
        assert self.calls[0].url.params["source"] == "arcmira_premium"
        assert self.calls[0].url.params["by"] == "person_1"

    async def test_component_ambiguous_resolution(self):
        component = ArcmiraEntityResolve()
        component.set(api_key="synthetic-native-key", query="John", context="podcast", entity_type="person", limit=8)
        body = {"candidates": [{"id": "a"}, {"id": "b"}], "needs_clarification": True, "suggested": None}
        with self.transport(body):
            output = await component.resolve_entity()
        assert output.data == body
        assert self.calls[0].url.params["type"] == "person"

    async def test_native_tool_artifact(self):
        component = ArcmiraTranscriptSearch()
        component.set(api_key="synthetic-native-key", source="arcmira_premium", limit=5)
        tools = await component.to_toolkit()
        assert len(tools) == 1
        body = {"chunks": [], "coverage": {"complete": False}, "access": {"plan": "pro_plus"}}
        with self.transport(body):
            output = await tools[0].ainvoke(
                {"name": tools[0].name, "args": {"query": "climate"}, "id": "fixture-tool-call", "type": "tool_call"}
            )
        assert output.artifact == body
        assert len(self.calls) == 1
        assert self.calls[0].url.params["q"] == "climate"
        assert self.calls[0].url.params["source"] == "arcmira_premium"

    async def test_native_refusal_no_caption_fallback(self):
        component = ArcmiraTranscriptSearch()
        component.set(api_key="synthetic-native-key", query="climate", source="arcmira_premium", limit=5)
        with (
            self.transport({"error": "insufficient_credits", "detail": "synthetic-native-key"}, 403),
            pytest.raises(ArcmiraReadError) as got,
        ):
            await component.search_transcripts()
        assert got.value.status == 403
        assert "synthetic-native-key" not in str(got.value)
        assert len(self.calls) == 1
        assert self.calls[0].url.params["source"] == "arcmira_premium"


if __name__ == "__main__":
    unittest.main(verbosity=2)
