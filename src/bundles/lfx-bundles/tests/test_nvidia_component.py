"""Tests for NVIDIAModelComponent lazy model loading.

Verifies that no network call is made at import/class-definition time,
and that model options are populated dynamically via update_build_config.
"""

import contextlib
import http.server
import json
import sys
import threading
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("lfx_bundles")


class TestNVIDIAModelComponentLazyLoading:
    """Ensure NVIDIA model list is fetched lazily, not at import time."""

    def test_model_options_empty_on_import(self):
        """The model_name dropdown should have no options at class definition time."""
        from lfx_bundles.nvidia.nvidia import NVIDIAModelComponent

        model_name_input = next(
            inp for inp in NVIDIAModelComponent.inputs if getattr(inp, "name", None) == "model_name"
        )
        assert model_name_input.options == [], (
            "model_name options must be empty at import time to avoid blocking network calls"
        )

    def test_no_network_call_during_import(self):
        """Importing the module must not instantiate ChatNVIDIA or call get_available_models."""
        import importlib
        import sys

        # Insert a mock module so the import succeeds even without the real package
        mock_nvidia_module = MagicMock()
        sys.modules["langchain_nvidia_ai_endpoints"] = mock_nvidia_module
        try:
            import lfx_bundles.nvidia.nvidia as nvidia_mod

            importlib.reload(nvidia_mod)

            # The class-level code must not call ChatNVIDIA() or get_available_models()
            mock_nvidia_module.ChatNVIDIA.assert_not_called()
            mock_nvidia_module.ChatNVIDIA.return_value.get_available_models.assert_not_called()
        finally:
            sys.modules.pop("langchain_nvidia_ai_endpoints", None)

    def test_update_build_config_populates_models(self):
        """update_build_config should fetch models and populate the dropdown options."""
        from lfx.schema.dotdict import dotdict
        from lfx_bundles.nvidia.nvidia import NVIDIAModelComponent

        fake_model_a = MagicMock()
        fake_model_a.id = "model-a"
        fake_model_a.supports_tools = False
        fake_model_b = MagicMock()
        fake_model_b.id = "model-b"
        fake_model_b.supports_tools = True

        component = NVIDIAModelComponent()
        component._attributes = {
            "base_url": "https://integrate.api.nvidia.com/v1",
            "api_key": "fake-key",  # pragma: allowlist secret
            "tool_model_enabled": False,
        }

        build_config = dotdict(
            {
                "model_name": {"options": [], "value": None},
                "detailed_thinking": {"value": False, "show": False},
            }
        )

        with patch("lfx_bundles.nvidia.nvidia.ChatNVIDIA", create=True) as mock_cls:
            mock_instance = MagicMock()
            mock_instance.available_models = [fake_model_a, fake_model_b]
            mock_instance.get_available_models.return_value = [fake_model_a, fake_model_b]
            mock_cls.return_value = mock_instance

            # Patch get_models to use our mock since the real import path may differ
            with patch.object(component, "get_models", return_value=["model-a", "model-b"]):
                result = component.update_build_config(build_config, None, field_name="model_name")

        assert result["model_name"]["options"] == ["model-a", "model-b"]
        assert result["model_name"]["value"] == "model-a"

    def test_update_build_config_handles_api_failure(self):
        """update_build_config should clear options and raise on API failure."""
        from lfx.schema.dotdict import dotdict
        from lfx_bundles.nvidia.nvidia import NVIDIAModelComponent

        component = NVIDIAModelComponent()
        component._attributes = {
            "base_url": "https://integrate.api.nvidia.com/v1",
            "api_key": "fake-key",  # pragma: allowlist secret
            "tool_model_enabled": False,
        }

        build_config = dotdict(
            {
                "model_name": {"options": ["stale-model"], "value": "stale-model"},
                "detailed_thinking": {"value": False, "show": False},
            }
        )

        with (
            patch.object(
                component,
                "get_models",
                side_effect=ConnectionError("network unreachable"),
            ),
            contextlib.suppress(ValueError),
        ):
            component.update_build_config(build_config, None, field_name="model_name")

        assert build_config["model_name"]["options"] == []
        assert build_config["model_name"]["value"] is None


class TestNVIDIACredentialEgress:
    """Credential-egress guard for the NVIDIA component (H1-4000668 / LE-2670).

    An operator key held only in the server environment must not be sent to a
    tenant-chosen base_url -- including on the model-discovery request, which
    fires before any inference call.
    """

    OPERATOR_KEY = "nvapi-operator-canary-b7c6d5e4"  # pragma: allowlist secret
    CUSTOM_URL = "https://attacker.example.com/v1"

    @pytest.fixture(autouse=True)
    def _no_dns_dependency(self, monkeypatch):
        """Neutralize the SSRF host lookup so these tests exercise the credential guard alone.

        ``validate_provider_base_url`` resolves the host, and the canary domain used here has
        no DNS record, so without this the "allowed" cases fail on resolution rather than
        reaching the guard under test. Same seam the shared-helper tests patch in
        ``src/lfx/tests/unit/base/models/test_provider_ssrf.py``.
        """
        monkeypatch.setattr(
            "lfx.base.models.provider_ssrf.validate_strict_url_for_ssrf_or_raise",
            lambda _url: None,
        )

    def _component(self, base_url: str, api_key: str):
        from lfx_bundles.nvidia.nvidia import NVIDIAModelComponent

        component = NVIDIAModelComponent()
        component._attributes = {
            "base_url": base_url,
            "api_key": api_key,
            "tool_model_enabled": False,
            "model_name": "model-a",
            "max_tokens": 10,
            "temperature": 0.1,
            "seed": 1,
        }
        return component

    def test_get_models_blocks_env_sourced_key_to_custom_host(self, monkeypatch):
        monkeypatch.setenv("NVIDIA_API_KEY", self.OPERATOR_KEY)
        monkeypatch.delenv("LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS", raising=False)
        component = self._component(self.CUSTOM_URL, self.OPERATOR_KEY)

        with pytest.raises(ValueError, match="server-provisioned API credential"):
            component.get_models()

    def test_build_model_blocks_env_sourced_key_to_custom_host(self, monkeypatch):
        monkeypatch.setenv("NVIDIA_API_KEY", self.OPERATOR_KEY)
        monkeypatch.delenv("LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS", raising=False)
        component = self._component(self.CUSTOM_URL, self.OPERATOR_KEY)

        with pytest.raises(ValueError, match="server-provisioned API credential"):
            component.build_model()

    def test_build_model_allows_env_sourced_key_to_default_endpoint(self, monkeypatch):
        monkeypatch.setenv("NVIDIA_API_KEY", self.OPERATOR_KEY)
        component = self._component("https://integrate.api.nvidia.com/v1", self.OPERATOR_KEY)

        mock_module = MagicMock()
        monkeypatch.setitem(sys.modules, "langchain_nvidia_ai_endpoints", mock_module)
        component.build_model()

        assert mock_module.ChatNVIDIA.call_args.kwargs["base_url"] == "https://integrate.api.nvidia.com/v1"

    def test_build_model_allows_tenant_owned_key_to_custom_host(self, monkeypatch):
        monkeypatch.delenv("LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS", raising=False)
        component = self._component(self.CUSTOM_URL, "nvapi-tenant-owned-1a2b3c4d")  # pragma: allowlist secret

        mock_module = MagicMock()
        monkeypatch.setitem(sys.modules, "langchain_nvidia_ai_endpoints", mock_module)
        component.build_model()

        assert mock_module.ChatNVIDIA.call_args.kwargs["base_url"] == self.CUSTOM_URL


class TestNVIDIAAbsentKeyCredentialEgress:
    """An absent NVIDIA key is not an absent credential (LE-2670 follow-up).

    ``ChatNVIDIA`` answers a missing ``api_key`` by reading ``NVIDIA_API_KEY`` from the
    server process environment, so leaving the field blank was a way around the guard.
    """

    OPERATOR_KEY = "nvapi-operator-canary-b7c6d5e4"  # pragma: allowlist secret
    CUSTOM_URL = "https://attacker.example.com/v1"

    def _component(self, base_url, api_key):
        from lfx_bundles.nvidia.nvidia import NVIDIAModelComponent

        component = NVIDIAModelComponent()
        component._attributes = {
            "base_url": base_url,
            "api_key": api_key,
            "tool_model_enabled": False,
            "model_name": "model-a",
            "max_tokens": 10,
            "temperature": 0.1,
            "seed": 1,
        }
        return component

    @pytest.fixture(autouse=True)
    def _no_allowlist(self, monkeypatch):
        monkeypatch.delenv("LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS", raising=False)
        monkeypatch.setattr(
            "lfx.base.models.provider_ssrf.validate_strict_url_for_ssrf_or_raise",
            lambda _url: None,
        )

    @pytest.mark.parametrize("absent", [None, ""])
    def test_build_model_blocks_absent_key_when_env_would_supply_one(self, absent, monkeypatch):
        monkeypatch.setenv("NVIDIA_API_KEY", self.OPERATOR_KEY)
        component = self._component(self.CUSTOM_URL, absent)

        with pytest.raises(ValueError, match=r"falls back to \$NVIDIA_API_KEY"):
            component.build_model()

    @pytest.mark.parametrize("absent", [None, ""])
    def test_get_models_blocks_absent_key_when_env_would_supply_one(self, absent, monkeypatch):
        monkeypatch.setenv("NVIDIA_API_KEY", self.OPERATOR_KEY)
        component = self._component(self.CUSTOM_URL, absent)

        with pytest.raises(ValueError, match=r"falls back to \$NVIDIA_API_KEY"):
            component.get_models()

    def test_build_model_allows_absent_key_when_env_var_is_unset(self, monkeypatch):
        """Nothing for the SDK to resolve means nothing of the operator's can leave."""
        monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
        component = self._component(self.CUSTOM_URL, None)

        mock_module = MagicMock()
        monkeypatch.setitem(sys.modules, "langchain_nvidia_ai_endpoints", mock_module)
        component.build_model()

        assert mock_module.ChatNVIDIA.call_args.kwargs["base_url"] == self.CUSTOM_URL


class _LoopbackHandler(http.server.BaseHTTPRequestHandler):
    """Base handler: silences logging and records what actually reached this server."""

    protocol_version = "HTTP/1.1"
    received: list[dict]

    def log_message(self, *args):  # noqa: ARG002 - silence the stderr access log
        return

    def _read_body(self) -> str:
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length).decode() if length else ""

    def _json(self, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _serve(handler_cls) -> tuple[Any, int]:
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]


@pytest.fixture
def redirect_endpoint():
    """A base_url that answers every request with a 307 to a second, unapproved port.

    Yields ``(base_url, received)`` where ``received`` is the list of requests that reached
    the *redirect target*. It must stay empty: nothing may be forwarded there, and in
    particular no prompt body.
    """
    received: list[dict] = []

    class Target(_LoopbackHandler):
        def _record(self):
            received.append(
                {
                    "path": self.path,
                    "authorization": self.headers.get("Authorization"),
                    "body": self._read_body(),
                }
            )
            self._json({"data": [{"id": "target-model", "object": "model"}]})

        def do_GET(self):
            self._record()

        def do_POST(self):
            self._record()

    target_server, target_port = _serve(Target)

    class Redirector(_LoopbackHandler):
        def _redirect(self):
            self.send_response(307)
            self.send_header("Location", f"http://127.0.0.1:{target_port}{self.path}")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self):
            self._redirect()

        def do_POST(self):
            self._redirect()

    redirect_server, redirect_port = _serve(Redirector)
    try:
        yield f"http://127.0.0.1:{redirect_port}/v1", received
    finally:
        redirect_server.shutdown()
        target_server.shutdown()


@pytest.fixture
def working_endpoint():
    """A base_url that answers normally, to prove the policy does not break ordinary calls."""
    served: list[str] = []

    class Endpoint(_LoopbackHandler):
        def do_GET(self):
            served.append(self.path)
            self._json({"data": [{"id": "ok-model", "object": "model"}]})

        def do_POST(self):
            served.append(self.path)
            if json.loads(self._read_body() or "{}").get("stream"):
                body = (
                    b'data: {"choices":[{"index":0,"delta":{"content":"he"}}]}\n\n'
                    b'data: {"choices":[{"index":0,"delta":{"content":"llo"}}]}\n\n'
                    b"data: [DONE]\n\n"
                )
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self._json(
                {
                    "id": "x",
                    "choices": [
                        {"index": 0, "message": {"role": "assistant", "content": "hello"}, "finish_reason": "stop"}
                    ],
                }
            )

    server, port = _serve(Endpoint)
    try:
        yield f"http://127.0.0.1:{port}/v1", served
    finally:
        server.shutdown()


@pytest.fixture
def redirect_policy():
    """Install the policy on the real pinned SDK and restore the class afterwards.

    The policy patches ``_NVIDIAClient`` itself -- that is the point, since the client issues
    a request from inside its own constructor -- so it has to be undone or it would leak into
    every later test in the session.
    """
    common = pytest.importorskip("langchain_nvidia_ai_endpoints._common")
    from lfx_bundles.nvidia.nvidia import _REDIRECT_POLICY_INSTALLED, _install_redirect_policy

    client_cls = common._NVIDIAClient
    saved = {
        "__init__": client_cls.__init__,
        "_create_session": client_cls._create_session,
        "_create_async_session": client_cls._create_async_session,
    }
    was_installed = getattr(client_cls, _REDIRECT_POLICY_INSTALLED, False)
    _install_redirect_policy()
    try:
        yield
    finally:
        for name, attr in saved.items():
            setattr(client_cls, name, attr)
        if not was_installed:
            with contextlib.suppress(AttributeError):
                delattr(client_cls, _REDIRECT_POLICY_INSTALLED)


@pytest.mark.usefixtures("redirect_policy")
class TestNVIDIARedirectPolicy:
    """Redirects must be refused on every NVIDIA transport, from the first request onward.

    ``requests`` and ``aiohttp`` both follow redirects by default and both keep the
    ``Authorization`` header across a same-host hop, so an endpoint the operator allowlisted
    could bounce the request -- key and prompt included -- to a port the endpoint guard never
    saw. These tests run the real pinned SDK against loopback servers; the assertion that
    matters in each is that the redirect target received nothing.
    """

    API_KEY = "nvapi-canary-0123456789"  # pragma: allowlist secret
    PROMPT = "SECRET_PROMPT_CANARY"

    @staticmethod
    def _chat(base_url: str, **kwargs):
        from langchain_nvidia_ai_endpoints import ChatNVIDIA

        return ChatNVIDIA(base_url=base_url, api_key=TestNVIDIARedirectPolicy.API_KEY, **kwargs)

    def test_constructor_discovery_refuses_redirect(self, redirect_endpoint):
        """ChatNVIDIA resolves available_models inside __init__, before any hook could run."""
        from lfx.utils.ssrf_protection import SSRFProtectionError

        base_url, received = redirect_endpoint

        with pytest.raises(SSRFProtectionError, match="Refusing to follow the redirect"):
            self._chat(base_url)

        assert received == [], "model discovery followed the redirect to an unapproved host"

    def test_sync_inference_refuses_redirect(self, redirect_endpoint):
        from lfx.utils.ssrf_protection import SSRFProtectionError

        base_url, received = redirect_endpoint
        model = self._chat(base_url, model="target-model")

        with pytest.raises(SSRFProtectionError, match="Refusing to follow the redirect"):
            model.invoke(self.PROMPT)

        assert received == []

    async def test_async_inference_refuses_redirect(self, redirect_endpoint):
        """_agenerate runs on aiohttp, which a requests-only hook leaves unprotected."""
        from lfx.utils.ssrf_protection import SSRFProtectionError

        base_url, received = redirect_endpoint
        model = self._chat(base_url, model="target-model")

        with pytest.raises(SSRFProtectionError, match="Refusing to follow the redirect"):
            await model.ainvoke(self.PROMPT)

        assert received == [], "async inference forwarded the request to the redirect target"
        assert all(self.PROMPT not in entry["body"] for entry in received)

    async def test_streaming_refuses_redirect(self, redirect_endpoint):
        from lfx.utils.ssrf_protection import SSRFProtectionError

        base_url, received = redirect_endpoint
        model = self._chat(base_url, model="target-model")

        with pytest.raises(SSRFProtectionError, match="Refusing to follow the redirect"):
            async for _ in model.astream(self.PROMPT):
                pass

        assert received == []

    async def test_ordinary_requests_still_work(self, working_endpoint):
        """The policy replaces redirect resolution only; normal traffic is untouched."""
        base_url, served = working_endpoint

        model = self._chat(base_url)
        assert model.model == "ok-model"  # resolved by constructor-time discovery
        assert model.invoke("hi").content == "hello"
        assert (await model.ainvoke("hi")).content == "hello"
        assert "".join([chunk.content async for chunk in model.astream("hi")]) == "hello"

        assert served == ["/v1/models"] + ["/v1/chat/completions"] * 3


class TestNVIDIARedirectPolicyFailsClosed:
    """A moved SDK seam must stop the request, not downgrade to an unprotected client."""

    def test_missing_client_class_refuses_to_build(self, monkeypatch):
        common = pytest.importorskip("langchain_nvidia_ai_endpoints._common")
        from lfx_bundles.nvidia.nvidia import _install_redirect_policy

        monkeypatch.delattr(common, "_NVIDIAClient", raising=False)

        with pytest.raises(ValueError, match="no longer exposes '_NVIDIAClient'"):
            _install_redirect_policy()

    def test_missing_session_factory_refuses_to_build(self, monkeypatch):
        common = pytest.importorskip("langchain_nvidia_ai_endpoints._common")
        from lfx_bundles.nvidia.nvidia import _install_redirect_policy

        class Moved:
            def _create_session(self):
                return None

        monkeypatch.setattr(common, "_NVIDIAClient", Moved)

        with pytest.raises(ValueError, match="no longer exposes its session factories"):
            _install_redirect_policy()

    def test_component_installs_policy_before_constructing_the_client(self, monkeypatch):
        """get_models must harden the SDK first: the client requests during construction."""
        from lfx_bundles.nvidia.nvidia import NVIDIAModelComponent

        order: list[str] = []
        monkeypatch.setattr(
            "lfx_bundles.nvidia.nvidia._install_redirect_policy",
            lambda: order.append("install"),
        )

        mock_module = MagicMock()
        mock_module.ChatNVIDIA.side_effect = lambda **_kwargs: order.append("construct") or MagicMock(
            available_models=[]
        )
        monkeypatch.setitem(sys.modules, "langchain_nvidia_ai_endpoints", mock_module)

        component = NVIDIAModelComponent()
        component._attributes = {
            "base_url": "https://integrate.api.nvidia.com/v1",
            "api_key": "nvapi-tenant-owned-1a2b3c4d",  # pragma: allowlist secret
            "tool_model_enabled": False,
        }
        component.get_models()

        assert order == ["install", "construct"]
