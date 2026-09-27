"""Positive SSRF-block regression tests for connector components with a tenant-controlled host.

These prove the SSRF guards added to the model-provider discovery fetches and the Glean tool
actually block an internal/metadata host BEFORE any outbound request is made. The only thing
mocked is the settings service (to turn SSRF protection on) and the network sink (as a sentinel
to assert it is never reached) — the real SSRF validation logic runs.

The vector-store connector guards (qdrant/elasticsearch/opensearch/milvus/supabase/
upstash/clickhouse/chroma) and astradb_cql use the shared connector SSRF validators, which are
exercised directly in ``lfx/tests/unit/utils/test_ssrf_protection.py``. The weaviate, redis chat
memory, confluence, nvidia, and sambanova guards (H1-3996328) are exercised below.
"""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("lfx_bundles")

METADATA_URL = "http://169.254.169.254"


@contextmanager
def ssrf_enabled():
    """Enable global and connector SSRF protection."""
    with patch("lfx.utils.ssrf_protection.get_settings_service") as mock_get:
        s = MagicMock()
        s.settings.ssrf_protection_enabled = True
        s.settings.connector_ssrf_validation_enabled = True
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


# H1-3996328: connectors that read a tenant-controlled URL/host and connected without ever
# calling the central SSRF guard. Each test pins the guard: the block must come from
# validate_connector_url_for_ssrf and the SDK sink must never be reached.


def test_weaviate_blocks_metadata_url_before_client_connect():
    from lfx.utils.ssrf_protection import SSRFProtectionError
    from lfx_bundles.weaviate.weaviate import WeaviateVectorStoreComponent

    component = WeaviateVectorStoreComponent(url=f"{METADATA_URL}:8080", index_name="Test")
    with ssrf_enabled(), patch("weaviate.connect_to_custom") as mock_connect, pytest.raises(SSRFProtectionError):
        component._connect_client()
    assert mock_connect.call_count == 0


def test_weaviate_blocks_metadata_grpc_host_before_client_connect():
    """A public-looking URL with a tenant-controlled internal grpc_host is still blocked."""
    from lfx.utils.ssrf_protection import SSRFProtectionError
    from lfx_bundles.weaviate.weaviate import WeaviateVectorStoreComponent

    component = WeaviateVectorStoreComponent(
        url="http://localhost:8080", index_name="Test", grpc_host="169.254.169.254"
    )
    with ssrf_enabled(), patch("weaviate.connect_to_custom") as mock_connect, pytest.raises(SSRFProtectionError):
        component._connect_client()
    assert mock_connect.call_count == 0


def test_redis_chat_memory_blocks_metadata_host_before_connect():
    from lfx.utils.ssrf_protection import SSRFProtectionError
    from lfx_bundles.redis.redis_chat import RedisIndexChatMemory

    component = RedisIndexChatMemory()
    component.host = "169.254.169.254"
    component.port = 6379
    component.database = "0"
    component.username = ""
    component.password = ""
    component.key_prefix = ""
    component.session_id = "test-session"
    with (
        ssrf_enabled(),
        patch("lfx_bundles.redis.redis_chat.RedisChatMessageHistory") as mock_history,
        pytest.raises(SSRFProtectionError),
    ):
        component.build_message_history()
    assert mock_history.call_count == 0


def test_confluence_blocks_metadata_url_before_loader():
    from lfx.utils.ssrf_protection import SSRFProtectionError
    from lfx_bundles.confluence.confluence import ConfluenceComponent

    component = ConfluenceComponent()
    component.url = f"{METADATA_URL}/wiki"
    component.username = "user@example.com"
    component.api_key = "test-key"
    component.space_key = "SPACE"
    component.cloud = True
    component.content_format = "storage"
    component.max_pages = 10
    with (
        ssrf_enabled(),
        patch("lfx_bundles.confluence.confluence.ConfluenceLoader") as mock_loader,
        pytest.raises(SSRFProtectionError),
    ):
        component.build_confluence()
    assert mock_loader.call_count == 0


def test_nvidia_build_model_blocks_metadata_url_before_sdk():
    from lfx.utils.ssrf_protection import SSRFProtectionError
    from lfx_bundles.nvidia.nvidia import NVIDIAModelComponent

    component = NVIDIAModelComponent()
    component._attributes = {
        "base_url": f"{METADATA_URL}/v1",
        "api_key": "test-key",  # pragma: allowlist secret
        "model_name": "model",
        "max_tokens": 1,
        "temperature": 0.1,
        "seed": 1,
    }
    with ssrf_enabled(), pytest.raises(SSRFProtectionError):
        component.build_model()


def test_nvidia_get_models_blocks_metadata_url_before_sdk():
    from lfx.utils.ssrf_protection import SSRFProtectionError
    from lfx_bundles.nvidia.nvidia import NVIDIAModelComponent

    component = NVIDIAModelComponent()
    component._attributes = {
        "base_url": f"{METADATA_URL}/v1",
        "api_key": "test-key",  # pragma: allowlist secret
        "tool_model_enabled": False,
    }
    with ssrf_enabled(), pytest.raises(SSRFProtectionError):
        component.get_models()


def test_sambanova_build_model_blocks_metadata_url_before_sdk():
    from lfx.utils.ssrf_protection import SSRFProtectionError
    from lfx_bundles.sambanova.sambanova import SambaNovaComponent

    component = SambaNovaComponent()
    component.base_url = f"{METADATA_URL}/v1/chat/completions"
    component.model_name = "Meta-Llama-3.1-8B-Instruct"
    component.api_key = "test-key"
    component.max_tokens = 16
    component.top_p = 1.0
    component.temperature = 0.1
    with (
        ssrf_enabled(),
        patch("lfx_bundles.sambanova.sambanova.ChatSambaNovaCloud") as mock_chat,
        pytest.raises(SSRFProtectionError),
    ):
        component.build_model()
    assert mock_chat.call_count == 0
