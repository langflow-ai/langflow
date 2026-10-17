"""A ``temperature`` of 0 is a meaningful, in-range value and must reach the provider SDK.

Every provider component below declares ``range_spec=RangeSpec(min=0, ...)`` on its
Temperature input, so 0 is a value the UI offers. ``temperature or <default>`` treats
that 0 as "unset" and silently substitutes the provider default, which makes a
deliberately deterministic model behave like a creative one. These tests pin the
``is None`` form so the fallback only applies when the user really left it empty.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("lfx_bundles")

# The provider SDKs are per-provider extras and are not installed in a bare
# lfx-bundles environment. The components only need the names to exist, so stub
# the modules before the component modules are imported.
for _name in (
    "langchain_community",
    "langchain_community.chat_models",
    "langchain_community.llms",
    "langchain_community.llms.huggingface_endpoint",
    "langchain_nvidia_ai_endpoints",
    "langchain_perplexity",
    "langchain_sambanova",
):
    sys.modules.setdefault(_name, MagicMock())


class TestPerplexityTemperature:
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


class TestHuggingFaceTemperature:
    def _build(self, temperature):
        from lfx_bundles.huggingface.huggingface import HuggingFaceEndpointsComponent

        component = HuggingFaceEndpointsComponent()
        component._attributes = {
            "huggingfacehub_api_token": "hf-test-key",  # pragma: allowlist secret
            "model_name": "meta-llama/Llama-3.3-70B-Instruct",
            "temperature": temperature,
            "max_new_tokens": None,
            "top_k": None,
            "top_p": None,
            "typical_p": None,
            "repetition_penalty": None,
            "model_kwargs": {},
            "task": None,
            "retry_attempts": 1,
        }
        with patch.object(HuggingFaceEndpointsComponent, "create_huggingface_endpoint") as mock_create:
            component.build_model()
        return mock_create.call_args.kwargs

    def test_zero_reaches_the_provider(self):
        assert self._build(0.0)["temperature"] == 0.0

    def test_unset_still_falls_back(self):
        assert self._build(None)["temperature"] == 0.8
