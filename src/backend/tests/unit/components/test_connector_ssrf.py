"""Positive SSRF-block regression tests for connector components with a tenant-controlled host.

These prove the SSRF guards added to the model-provider discovery fetches and the Glean tool
actually block an internal/metadata host BEFORE any outbound request is made. The only thing
mocked is the settings service (to turn SSRF protection on) and the network sink (as a sentinel
to assert it is never reached) — the real SSRF validation logic runs.

The vector-store connector guards (qdrant/weaviate/elasticsearch/opensearch/milvus/supabase/
upstash/clickhouse/chroma) and astradb_cql use the shared connector SSRF validators, which are
exercised directly in ``lfx/tests/unit/utils/test_ssrf_protection.py``.
"""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

METADATA_URL = "http://169.254.169.254"


@contextmanager
def ssrf_enabled():
    """Enable both global SSRF protection AND the opt-in connector-SSRF validation flag."""
    with patch("lfx.utils.ssrf_protection.get_settings_service") as mock_get:
        s = MagicMock()
        s.settings.ssrf_protection_enabled = True
        s.settings.connector_ssrf_validation_enabled = True  # opt-in gate for connector components
        s.settings.ssrf_allowed_hosts = []
        s.settings.restrict_local_file_access = False
        mock_get.return_value = s
        yield


def test_deepseek_get_models_blocks_metadata_without_request():
    """Deepseek returns its default model list on block — and never hits the host."""
    from lfx.components.deepseek.deepseek import DEEPSEEK_MODELS, DeepSeekModelComponent

    component = DeepSeekModelComponent()
    component.api_key = "test-key"  # required, else get_models early-returns without fetching
    component.api_base = METADATA_URL
    with ssrf_enabled(), patch("httpx.Client.get") as mock_get:
        result = component.get_models()
        assert mock_get.call_count == 0
        assert result == DEEPSEEK_MODELS


def test_xai_get_models_blocks_metadata_without_request():
    from lfx.components.xai.xai import XAI_DEFAULT_MODELS, XAIModelComponent

    component = XAIModelComponent()
    component.api_key = "test-key"
    component.base_url = METADATA_URL
    with ssrf_enabled(), patch("httpx.Client.get") as mock_get:
        result = component.get_models()
        assert mock_get.call_count == 0
        assert result == XAI_DEFAULT_MODELS


def test_litellm_proxy_blocks_metadata_without_request():
    """Litellm raises (ValueError) on block, before the httpx request."""
    from lfx.components.litellm.litellm_proxy import LiteLLMProxyComponent

    component = LiteLLMProxyComponent()
    component.api_base = METADATA_URL
    with (
        ssrf_enabled(),
        patch("httpx.Client.get") as mock_get,
        pytest.raises(ValueError, match="SSRF"),
    ):
        component._validate_proxy_connection("test-key")
    assert mock_get.call_count == 0


def test_huggingface_inference_endpoint_blocks_metadata_without_request():
    from lfx.components.huggingface.huggingface_inference_api import HuggingFaceInferenceAPIEmbeddingsComponent

    component = HuggingFaceInferenceAPIEmbeddingsComponent()
    component.inference_endpoint = METADATA_URL
    with (
        ssrf_enabled(),
        patch("httpx.Client.get") as mock_get,
        pytest.raises(ValueError, match="SSRF"),
    ):
        component.validate_inference_endpoint(METADATA_URL)
    assert mock_get.call_count == 0


def test_glean_blocks_metadata_before_token_sent():
    """Glean raises before the bearer token is attached to a request to a blocked host."""
    from lfx.components.glean.glean_search_api import GleanAPIWrapper
    from lfx.utils.ssrf_protection import SSRFProtectionError

    wrapper = GleanAPIWrapper(glean_api_url=METADATA_URL, glean_access_token="secret-token")  # noqa: S106 - test token
    with ssrf_enabled(), patch("httpx.Client.post") as mock_post, pytest.raises(SSRFProtectionError):
        wrapper._search_api_results("query")
    assert mock_post.call_count == 0
