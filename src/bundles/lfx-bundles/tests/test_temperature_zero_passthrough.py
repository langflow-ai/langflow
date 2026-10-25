"""A ``temperature`` of 0 is a meaningful, in-range value and must reach the provider SDK.

Every provider component below declares ``range_spec=RangeSpec(min=0, ...)`` on its
Temperature input, so 0 is a value the UI offers. ``temperature or <default>`` treats
that 0 as "unset" and silently substitutes the provider default, which makes a
deliberately deterministic model behave like a creative one. These tests pin the
``is None`` form so the fallback only applies when the user really left it empty.
"""

from unittest.mock import patch

import pytest

pytest.importorskip("lfx_bundles")


class TestPerplexityTemperature:
    @pytest.fixture(autouse=True)
    def require_provider_sdk(self):
        pytest.importorskip("langchain_perplexity")

    def _build(self, temperature):
        from lfx_bundles.perplexity.perplexity import PerplexityComponent

        component = PerplexityComponent()
        component._attributes = {
            "api_key": "pplx-test-key",  # pragma: allowlist secret
            "model_name": "sonar",
            "temperature": temperature,
            "max_tokens": None,
            "top_p": None,
            "n": 1,
        }
        with patch("lfx_bundles.perplexity.perplexity.ChatPerplexity", create=True) as mock_cls:
            component.build_model()
        return mock_cls.call_args.kwargs

    def test_zero_reaches_the_provider(self):
        assert self._build(0.0)["temperature"] == 0.0

    def test_unset_still_falls_back(self):
        assert self._build(None)["temperature"] == 0.75


class TestSambaNovaTemperature:
    @pytest.fixture(autouse=True)
    def require_provider_sdk(self):
        pytest.importorskip("langchain_sambanova")

    def _build(self, temperature):
        from lfx_bundles.sambanova.sambanova import SambaNovaComponent

        component = SambaNovaComponent()
        component._attributes = {
            "sambanova_api_key": "samba-test-key",  # pragma: allowlist secret
            "sambanova_url": "https://api.sambanova.ai/v1",
            "model_name": "Meta-Llama-3.1-8B-Instruct",
            "temperature": temperature,
            "max_tokens": None,
            "top_p": None,
        }
        with patch("lfx_bundles.sambanova.sambanova.ChatSambaNova", create=True) as mock_cls:
            component.build_model()
        return mock_cls.call_args.kwargs

    def test_zero_reaches_the_provider(self):
        assert self._build(0.0)["temperature"] == 0.0

    def test_unset_still_falls_back(self):
        assert self._build(None)["temperature"] == 0.07


class TestNVIDIATemperature:
    @pytest.fixture(autouse=True)
    def require_provider_sdk(self):
        pytest.importorskip("langchain_nvidia_ai_endpoints")

    def _build(self, temperature):
        from lfx_bundles.nvidia.nvidia import NVIDIAModelComponent

        component = NVIDIAModelComponent()
        component._attributes = {
            "api_key": "nvapi-test-key",  # pragma: allowlist secret
            "base_url": "https://integrate.api.nvidia.com/v1",
            "model_name": "meta/llama-3.1-8b-instruct",
            "temperature": temperature,
            "max_tokens": None,
            "seed": None,
        }
        with patch("langchain_nvidia_ai_endpoints.ChatNVIDIA", create=True) as mock_cls:
            component.build_model()
        return mock_cls.call_args.kwargs

    def test_zero_reaches_the_provider(self):
        assert self._build(0.0)["temperature"] == 0.0

    def test_unset_still_falls_back(self):
        assert self._build(None)["temperature"] == 0.1


class TestMaritalkTemperature:
    @pytest.fixture(autouse=True)
    def require_provider_sdk(self):
        pytest.importorskip("langchain_community")

    def _build(self, temperature):
        from lfx_bundles.maritalk.maritalk import MaritalkModelComponent

        component = MaritalkModelComponent()
        component._attributes = {
            "api_key": "maritalk-test-key",  # pragma: allowlist secret
            "model_name": "sabia-3",
            "temperature": temperature,
            "max_tokens": None,
        }
        with patch("lfx_bundles.maritalk.maritalk.ChatMaritalk", create=True) as mock_cls:
            component.build_model()
        return mock_cls.call_args.kwargs

    def test_zero_reaches_the_provider(self):
        assert self._build(0.0)["temperature"] == 0.0

    def test_unset_still_falls_back(self):
        assert self._build(None)["temperature"] == 0.1
