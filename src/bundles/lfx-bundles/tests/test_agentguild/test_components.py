"""Agent Guild components exercise native LFX and offline HTTP transports."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import lfx_bundles
import pytest
from lfx.extension import load_lfx_bundles_extensions
from lfx.schema.data import Data
from lfx_bundles.agentguild import AgentGuildPaidOperations, AgentGuildPreflight
from lfx_bundles.agentguild import agentguild_common as common

pytestmark = pytest.mark.unit

PREFLIGHT = {
    "verdict": "delegate_with_caution",
    "failed": ["agent_card_signed"],
    "unknowns": ["independent_evidence"],
    "checks": [{"name": "endpoint_reachable", "status": "passed"}],
}
CATALOG = {"operations": [{"operation": "deep_preflight", "price_credits": 10, "free_alternative": "preflight"}]}


@pytest.fixture
def http_fixture(monkeypatch):
    """Use a real HTTPX client and response stream, with no network transport."""
    original_client = httpx.AsyncClient
    calls = []
    options = []

    def install(handler):
        def recorded(request):
            calls.append(request)
            assert request.url.host == "agent-guild-5d5r.onrender.com"
            assert request.method == "GET"
            assert "authorization" not in request.headers
            assert "x-api-key" not in request.headers
            return handler(request)

        def factory(**kwargs):
            options.append(kwargs)
            return original_client(transport=httpx.MockTransport(recorded), **kwargs)

        monkeypatch.setattr(common.httpx, "AsyncClient", factory)
        return calls, options

    return install


class TestAgentGuildPreflight:
    async def test_preflight_preserves_evidence_and_encodes_target(self, http_fixture):
        calls, options = http_fixture(lambda _: httpx.Response(200, json=PREFLIGHT))
        component = AgentGuildPreflight()
        component.set(url="https://agent.example/a2a?mode=read&capability=research", timeout=12)
        result = await component.inspect_endpoint()
        assert isinstance(result, Data)
        assert result.data == PREFLIGHT
        assert calls[0].url.path == "/preflight"
        assert calls[0].url.params["url"] == "https://agent.example/a2a?mode=read&capability=research"
        assert len(calls) == 1
        assert options == [{"timeout": 12, "follow_redirects": False, "trust_env": False}]

    @pytest.mark.parametrize(
        "target",
        [
            "",
            "   ",
            "file:///etc/passwd",
            "https://",
            "https://agent.example:0/a2a",
            "https://agent.example:bad/a2a",
            "https://user:pass@agent.example/a2a",
            "https://user@agent.example/a2a",
            "https://agent.example/a2a?api_key=secret",
            "https://agent.example/a2a?access_token=secret",
            "https://agent.example/a2a?%61pi-key=secret",
            "https://agent.example/a2a?X-Amz-Credential=secret",
            "https://agent.example/a2a#secret",
            "https://agent.example/\ncredential",
            "http://127.0.0.1/a2a",
            "http://[::1]/a2a",
            "http://192.168.1.1/a2a",
            "http://localhost/a2a",
            "http://service.local/a2a",
            "https://agent.example/" + "a" * 4096,
        ],
    )
    async def test_invalid_or_credential_targets_fail_before_transmission(self, target, http_fixture):
        calls, _ = http_fixture(lambda _: pytest.fail("Invalid target was transmitted"))
        component = AgentGuildPreflight()
        component.set(url=target)
        with pytest.raises(ValueError, match=r"URL|public endpoint"):
            await component.inspect_endpoint()
        assert calls == []

    @pytest.mark.parametrize("payload", [{}, {"verdict": "allow"}, {**PREFLIGHT, "unknowns": "missing"}])
    async def test_incomplete_preflight_is_rejected(self, payload, http_fixture):
        http_fixture(lambda _: httpx.Response(200, json=payload))
        component = AgentGuildPreflight()
        component.set(url="https://agent.example/a2a")
        with pytest.raises(TypeError, match="without verdict"):
            await component.inspect_endpoint()


class TestAgentGuildPaidOperations:
    async def test_prices_read_manifest_catalog_only(self, http_fixture):
        calls, _ = http_fixture(lambda _: httpx.Response(200, json={"paid_operations": CATALOG, "other": "metadata"}))
        result = await AgentGuildPaidOperations().read_prices()
        assert result.data == CATALOG
        assert len(calls) == 1
        assert calls[0].url.path == "/.well-known/agent-guild.json"
        assert not calls[0].url.query

    @pytest.mark.parametrize("payload", [{}, {"paid_operations": []}, {"paid_operations": {"operations": "missing"}}])
    async def test_incomplete_catalog_is_rejected(self, payload, http_fixture):
        http_fixture(lambda _: httpx.Response(200, json=payload))
        with pytest.raises(TypeError, match="without a paid-operation catalog"):
            await AgentGuildPaidOperations().read_prices()


class TestAgentGuildTransport:
    @pytest.mark.parametrize("timeout", [0, -1, 61, True, 1.5, "30", None])
    async def test_timeout_is_bounded_before_client_creation(self, timeout, http_fixture):
        calls, options = http_fixture(lambda _: pytest.fail("Invalid timeout sent a request"))
        with pytest.raises(ValueError, match="1 to 60"):
            await common.read_json("/preflight", timeout=timeout)
        assert calls == options == []

    @pytest.mark.parametrize("status", [301, 302, 307, 308, 400, 402, 404, 500])
    async def test_http_failures_never_follow_redirects_or_pay(self, status, http_fixture):
        calls, _ = http_fixture(lambda _: httpx.Response(status, headers={"Location": "http://127.0.0.1/private"}))
        with pytest.raises(ValueError, match=f"HTTP {status}"):
            await common.read_json("/.well-known/agent-guild.json", timeout=30)
        assert len(calls) == 1

    @pytest.mark.parametrize("body", [b"not json", b"[]", b'"string"', b'{"value":NaN}', b"\xff"])
    async def test_malformed_json_is_not_evidence(self, body, http_fixture):
        http_fixture(lambda _: httpx.Response(200, content=body))
        with pytest.raises((ValueError, TypeError), match=r"JSON|response shape"):
            await common.read_json("/preflight", timeout=30)

    async def test_oversized_response_is_rejected(self, http_fixture):
        http_fixture(lambda _: httpx.Response(200, content=b" " * (common.MAX_RESPONSE_BYTES + 1)))
        with pytest.raises(ValueError, match="4 MiB"):
            await common.read_json("/preflight", timeout=30)

    async def test_transport_timeout_is_reported(self, http_fixture):
        def timed_out(request):
            msg = "fixture"
            raise httpx.ReadTimeout(msg, request=request)

        http_fixture(timed_out)
        with pytest.raises(ValueError, match="timed out"):
            await common.read_json("/preflight", timeout=30)

    async def test_total_deadline_cancels_slow_stream(self, http_fixture):
        closed = []

        class SlowStream(httpx.AsyncByteStream):
            async def __aiter__(self):
                while True:
                    yield b" "
                    await asyncio.sleep(0.05)

            async def aclose(self):
                closed.append(True)

        http_fixture(lambda _: httpx.Response(200, stream=SlowStream()))
        with pytest.raises(ValueError, match="timed out"):
            await common.read_json("/preflight", timeout=1)
        assert closed

    async def test_only_free_routes_are_available(self, http_fixture):
        calls, _ = http_fixture(lambda _: pytest.fail("A non-discovery route was called"))
        with pytest.raises(ValueError, match="Unsupported"):
            await common.read_json("/check", timeout=30)
        assert calls == []


class TestAgentGuildNativeIntegration:
    @pytest.mark.parametrize(
        ("component_class", "method", "arguments", "payload"),
        [
            (AgentGuildPreflight, "inspect_endpoint", {"url": "https://agent.example/a2a"}, PREFLIGHT),
            (AgentGuildPaidOperations, "read_prices", {"timeout": 15}, {"paid_operations": CATALOG}),
        ],
    )
    async def test_native_component_tool_execution(self, component_class, method, arguments, payload, http_fixture):
        calls, _ = http_fixture(lambda _: httpx.Response(200, json=payload))
        component = component_class()
        tools = await component.to_toolkit()
        assert len(tools) == 1
        assert tools[0].name == method
        assert set(tools[0].args) == set(arguments)
        result = await tools[0].ainvoke(arguments)
        serialized = json.dumps(result) if isinstance(result, dict) else str(result)
        assert "operations" in serialized if method == "read_prices" else "independent_evidence" in serialized
        assert len(calls) == 1

    @pytest.mark.parametrize("component_class", [AgentGuildPreflight, AgentGuildPaidOperations])
    def test_native_editor_metadata(self, component_class):
        component = component_class()
        node = component.to_frontend_node()
        assert node["data"]["node"]["icon"] == "AgentGuild"
        assert node["data"]["node"]["display_name"].startswith("Agent Guild")

    def test_official_bundle_discovery(
        self,
    ):
        """Exercise the installed entry point while shadowing unrelated providers."""
        root = Path(lfx_bundles.__file__).parent
        claimed = {
            path.name: ("installed", "unrelated-provider-fixture")
            for path in root.iterdir()
            if path.is_dir() and path.name != "agentguild"
        }
        results = load_lfx_bundles_extensions(claimed_bundles=claimed)
        matching = [result for result in results if result.bundle == "agentguild"]
        assert len(matching) == 1
        assert matching[0].errors == []
        assert {component.namespaced_id for component in matching[0].components} == {
            "ext:agentguild:AgentGuildPreflight@official",
            "ext:agentguild:AgentGuildPaidOperations@official",
        }
