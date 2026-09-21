"""Tests for NVIDIAModelComponent lazy model loading.

Verifies that no network call is made at import/class-definition time,
and that model options are populated dynamically via update_build_config.
"""

import contextlib
import sys
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


class TestNVIDIARedirectHandling:
    """ChatNVIDIA owns a ``requests.Session``, which follows redirects by default.

    ``requests`` only drops the Authorization header when a redirect changes the
    *hostname*, so a same-host redirect -- including one that switches port or downgrades
    to cleartext http -- carries the API key to a destination the endpoint guard never
    validated. Every other guarded provider takes redirect-free httpx clients; this one
    has to be hardened on the session itself.
    """

    @staticmethod
    def _fake_chat_nvidia_module(*, with_session_factory=True):
        """A stand-in for the SDK whose client mirrors ``_NVIDIAClient``'s session factory."""
        import requests

        module = MagicMock()
        client = MagicMock()
        if with_session_factory:
            client.get_session_fn = requests.Session
        else:
            del client.get_session_fn
        model = MagicMock()
        model._client = client
        del model._async_client
        module.ChatNVIDIA.return_value = model
        return module

    @staticmethod
    def _redirect_response():
        response = MagicMock()
        response.status_code = 302
        response.headers = {"Location": "http://integrate.api.nvidia.com:9999/internal"}
        response.url = "https://integrate.api.nvidia.com/v1/chat/completions"
        response.is_redirect = True
        return response

    def _component(self):
        from lfx_bundles.nvidia.nvidia import NVIDIAModelComponent

        component = NVIDIAModelComponent()
        component._attributes = {
            "base_url": "https://integrate.api.nvidia.com/v1",
            "api_key": "nvapi-tenant-owned-1a2b3c4d",  # pragma: allowlist secret
            "tool_model_enabled": False,
            "model_name": "model-a",
            "max_tokens": 10,
            "temperature": 0.1,
            "seed": 1,
        }
        return component

    def test_build_model_session_refuses_a_same_host_redirect(self, monkeypatch):
        from lfx.utils.ssrf_protection import SSRFProtectionError

        module = self._fake_chat_nvidia_module()
        monkeypatch.setitem(sys.modules, "langchain_nvidia_ai_endpoints", module)

        model = self._component().build_model()

        session = model._client.get_session_fn()
        with pytest.raises(SSRFProtectionError, match="Refusing to follow the redirect"):
            list(session.resolve_redirects(self._redirect_response(), MagicMock()))

    def test_get_models_session_refuses_a_same_host_redirect(self, monkeypatch):
        """Model discovery fires before any inference call and must be hardened too."""
        from lfx.utils.ssrf_protection import SSRFProtectionError

        module = self._fake_chat_nvidia_module()
        model = module.ChatNVIDIA.return_value
        model.available_models = []
        monkeypatch.setitem(sys.modules, "langchain_nvidia_ai_endpoints", module)

        self._component().get_models()

        session = model._client.get_session_fn()
        with pytest.raises(SSRFProtectionError, match="Refusing to follow the redirect"):
            list(session.resolve_redirects(self._redirect_response(), MagicMock()))

    def test_session_still_serves_non_redirect_responses(self, monkeypatch):
        module = self._fake_chat_nvidia_module()
        monkeypatch.setitem(sys.modules, "langchain_nvidia_ai_endpoints", module)

        model = self._component().build_model()

        ok = MagicMock()
        ok.is_redirect = False
        assert list(model._client.get_session_fn().resolve_redirects(ok, MagicMock())) == []

    def test_warns_when_the_sdk_stops_exposing_the_session_factory(self, monkeypatch):
        """A silent fail-open on an SDK bump is the thing to avoid; make it loud."""
        import lfx_bundles.nvidia.nvidia as nvidia_mod

        module = self._fake_chat_nvidia_module(with_session_factory=False)
        monkeypatch.setitem(sys.modules, "langchain_nvidia_ai_endpoints", module)
        warnings = []
        monkeypatch.setattr(nvidia_mod.logger, "warning", warnings.append)

        self._component().build_model()

        assert any("no longer exposes 'get_session_fn'" in message for message in warnings)
