from unittest.mock import patch

import pytest

pytest.importorskip("lfx_bundles")

from lfx.components.deepseek.deepseek import DEEPSEEK_MODELS, DeepSeekModelComponent
from lfx.components.glean.glean_search_api import GleanAPIWrapper
from lfx.components.homeassistant.home_assistant_control import HomeAssistantControl
from lfx.components.homeassistant.list_home_assistant_states import ListHomeAssistantStates
from lfx.components.huggingface.huggingface_inference_api import HuggingFaceInferenceAPIEmbeddingsComponent
from lfx.components.litellm.litellm_proxy import LiteLLMProxyComponent
from lfx.components.lmstudio.lmstudioembeddings import LMStudioEmbeddingsComponent
from lfx.components.lmstudio.lmstudiomodel import LMStudioModelComponent
from lfx.components.xai.xai import XAI_DEFAULT_MODELS, XAIModelComponent
from lfx.utils.ssrf_protection import SSRFProtectionError

BLOCKED_URL = "http://169.254.169.254/latest/meta-data"


@pytest.fixture(autouse=True)
def enable_ssrf_protection(monkeypatch):
    monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
    monkeypatch.delenv("LANGFLOW_SSRF_ALLOWED_HOSTS", raising=False)


@pytest.mark.asyncio
async def test_lmstudio_model_update_blocks_metadata_url_before_httpx():
    component = LMStudioModelComponent()
    build_config = {"base_url": {"load_from_db": False, "value": BLOCKED_URL}, "model_name": {"options": []}}

    with patch("httpx.AsyncClient.get") as mock_get, pytest.raises(ValueError, match="SSRF Protection"):
        await component.update_build_config(build_config, None, "model_name")

    mock_get.assert_not_called()


def test_lmstudio_model_build_blocks_metadata_url_before_openai_client():
    component = LMStudioModelComponent(base_url=BLOCKED_URL, model_name="model", api_key="test")

    with (
        patch("lfx.components.lmstudio.lmstudiomodel.ChatOpenAI") as mock_chat_openai,
        pytest.raises(ValueError, match="SSRF Protection"),
    ):
        component.build_model()

    mock_chat_openai.assert_not_called()


def test_lmstudio_embeddings_build_blocks_metadata_url_before_sdk_client():
    component = LMStudioEmbeddingsComponent(base_url=BLOCKED_URL, model="model", api_key="test")

    with (
        patch("lfx.components.lmstudio.lmstudioembeddings.NVIDIAEmbeddings", create=True) as mock_embeddings,
        pytest.raises(ValueError, match="SSRF Protection"),
    ):
        component.build_embeddings()

    mock_embeddings.assert_not_called()


def test_home_assistant_list_states_blocks_metadata_url_before_httpx():
    component = ListHomeAssistantStates()

    with patch("httpx.Client.get") as mock_get:
        result = component._list_states("token", BLOCKED_URL)

    assert "SSRF Protection" in result
    mock_get.assert_not_called()


def test_home_assistant_control_blocks_metadata_url_before_httpx():
    component = HomeAssistantControl()

    with patch("httpx.Client.post") as mock_post:
        result = component._control_device("token", BLOCKED_URL, "turn_on", "switch.test")

    assert "SSRF Protection" in result
    mock_post.assert_not_called()


def test_deepseek_model_fetch_blocks_metadata_url_before_httpx():
    component = DeepSeekModelComponent(api_base=BLOCKED_URL, api_key="test")

    with patch("httpx.Client.get") as mock_get:
        models = component.get_models()

    assert models == DEEPSEEK_MODELS
    assert "SSRF Protection" in component.status
    mock_get.assert_not_called()


def test_deepseek_build_blocks_metadata_url_before_openai_client():
    component = DeepSeekModelComponent(api_base=BLOCKED_URL, api_key="test")

    with patch("langchain_openai.ChatOpenAI") as mock_chat_openai, pytest.raises(ValueError, match="SSRF Protection"):
        component.build_model()

    mock_chat_openai.assert_not_called()


def test_xai_model_fetch_blocks_metadata_url_before_httpx():
    component = XAIModelComponent(base_url=BLOCKED_URL, api_key="test")

    with patch("httpx.Client.get") as mock_get:
        models = component.get_models()

    assert models == XAI_DEFAULT_MODELS
    assert "SSRF Protection" in component.status
    mock_get.assert_not_called()


def test_xai_build_blocks_metadata_url_before_openai_client():
    component = XAIModelComponent(base_url=BLOCKED_URL, api_key="test")

    with (
        patch("lfx.components.xai.xai.ChatOpenAI") as mock_chat_openai,
        pytest.raises(ValueError, match="SSRF Protection"),
    ):
        component.build_model()

    mock_chat_openai.assert_not_called()


def test_glean_blocks_metadata_url_before_httpx_post():
    wrapper = GleanAPIWrapper(glean_api_url=BLOCKED_URL, glean_access_token="test-access-token")  # noqa: S106

    with patch("httpx.Client.post") as mock_post, pytest.raises(SSRFProtectionError):
        wrapper._search_api_results("query")

    mock_post.assert_not_called()


def test_huggingface_build_blocks_metadata_url_before_sdk_client():
    component = HuggingFaceInferenceAPIEmbeddingsComponent(
        inference_endpoint=BLOCKED_URL,
        model_name="model",
    )

    with (
        patch.object(component, "create_huggingface_embeddings") as mock_create,
        pytest.raises(ValueError, match="SSRF Protection"),
    ):
        component.build_embeddings()

    mock_create.assert_not_called()


# The Ollama SSRF regressions live in the backend suite
# (src/backend/tests/unit/components/test_ssrf_guarded_ollama_components.py): Ollama graduated
# into lfx-ollama, a default langflow dependency, so those tests run without this bundle and
# lfx_ollama is not installed here.


def test_litellm_build_blocks_metadata_url_before_httpx_and_openai_client():
    component = LiteLLMProxyComponent(api_base=BLOCKED_URL, api_key="test", model_name="model")

    with (
        patch("httpx.Client.get") as mock_get,
        patch("lfx.components.litellm.litellm_proxy.ChatOpenAI") as mock_chat_openai,
        pytest.raises(ValueError, match="SSRF Protection"),
    ):
        component.build_model()

    mock_get.assert_not_called()
    mock_chat_openai.assert_not_called()


def test_aiml_build_blocks_metadata_url_before_openai_client():
    from lfx_bundles.aiml.aiml import AIMLModelComponent

    component = AIMLModelComponent(aiml_api_base=BLOCKED_URL, model_name="model", api_key="test")

    with (
        patch("lfx_bundles.aiml.aiml.ChatOpenAI") as mock_chat_openai,
        pytest.raises(ValueError, match="SSRF Protection"),
    ):
        component.build_model()

    mock_chat_openai.assert_not_called()


def test_aiml_build_default_base_url_still_constructs_client():
    from lfx_bundles.aiml.aiml import AIMLModelComponent

    component = AIMLModelComponent(model_name="model", api_key="test")

    with patch("lfx_bundles.aiml.aiml.ChatOpenAI") as mock_chat_openai:
        component.build_model()

    mock_chat_openai.assert_called_once()
    assert mock_chat_openai.call_args.kwargs["base_url"] == "https://api.aimlapi.com/v2"
    assert "http_client" not in mock_chat_openai.call_args.kwargs


def test_groq_build_blocks_metadata_url_before_groq_client():
    langchain_groq = pytest.importorskip("langchain_groq")
    from lfx_bundles.groq.groq import GroqModel

    component = GroqModel(base_url=BLOCKED_URL, model_name="model", api_key="test")

    with (
        patch.object(langchain_groq, "ChatGroq") as mock_chat_groq,
        pytest.raises(ValueError, match="SSRF Protection"),
    ):
        component.build_model()

    mock_chat_groq.assert_not_called()


def test_nvidia_build_blocks_metadata_url_before_sdk_client():
    pytest.importorskip("langchain_nvidia_ai_endpoints")
    from lfx_bundles.nvidia.nvidia import NVIDIAModelComponent

    component = NVIDIAModelComponent(base_url=BLOCKED_URL, model_name="model", api_key="test")

    with (
        patch("langchain_nvidia_ai_endpoints.ChatNVIDIA") as mock_chat_nvidia,
        pytest.raises(ValueError, match="SSRF Protection"),
    ):
        component.build_model()

    mock_chat_nvidia.assert_not_called()


def test_nvidia_model_fetch_blocks_metadata_url_before_sdk_client():
    pytest.importorskip("langchain_nvidia_ai_endpoints")
    from lfx_bundles.nvidia.nvidia import NVIDIAModelComponent

    component = NVIDIAModelComponent(base_url=BLOCKED_URL, api_key="test")

    with (
        patch("langchain_nvidia_ai_endpoints.ChatNVIDIA") as mock_chat_nvidia,
        pytest.raises(ValueError, match="SSRF Protection"),
    ):
        component.get_models()

    mock_chat_nvidia.assert_not_called()


def test_nvidia_embeddings_build_blocks_metadata_url_before_sdk_client():
    pytest.importorskip("langchain_nvidia_ai_endpoints")
    from lfx_bundles.nvidia.nvidia_embedding import NVIDIAEmbeddingsComponent

    component = NVIDIAEmbeddingsComponent(base_url=BLOCKED_URL, model="nvidia/nv-embed-v1", nvidia_api_key="test")

    with (
        patch("langchain_nvidia_ai_endpoints.NVIDIAEmbeddings") as mock_embeddings,
        pytest.raises(ValueError, match="SSRF Protection"),
    ):
        component.build_embeddings()

    mock_embeddings.assert_not_called()


def test_nvidia_rerank_build_blocks_metadata_url_before_sdk_client():
    pytest.importorskip("langchain_nvidia_ai_endpoints")
    from lfx_bundles.nvidia.nvidia_rerank import NvidiaRerankComponent

    component = NvidiaRerankComponent(base_url=BLOCKED_URL, model="nv-rerank-qa-mistral-4b:1", api_key="test")

    with (
        patch("langchain_nvidia_ai_endpoints.NVIDIARerank") as mock_rerank,
        pytest.raises(ValueError, match="SSRF Protection"),
    ):
        component.build_compressor()

    mock_rerank.assert_not_called()


def test_nvidia_ingest_blocks_metadata_url_before_ingestor(tmp_path):
    # importorskip on the submodule so the Ingestor patch target is importable
    pytest.importorskip("nv_ingest_client.client")

    from lfx_bundles.nvidia.nvidia_ingest import NvidiaIngestComponent

    component = NvidiaIngestComponent(base_url=BLOCKED_URL, api_key="test")
    doc = tmp_path / "doc.txt"
    doc.write_text("hello")
    base_file = NvidiaIngestComponent.BaseFile(data=[], path=doc)

    with (
        patch("nv_ingest_client.client.Ingestor") as mock_ingestor,
        pytest.raises(ValueError, match="SSRF Protection"),
    ):
        component.process_files([base_file])

    mock_ingestor.assert_not_called()


def test_mistral_embeddings_build_blocks_metadata_url_before_sdk_client():
    pytest.importorskip("langchain_mistralai")
    from lfx_bundles.mistral.mistral_embeddings import MistralAIEmbeddingsComponent

    component = MistralAIEmbeddingsComponent(endpoint=BLOCKED_URL, mistral_api_key="test")

    with (
        patch("lfx_bundles.mistral.mistral_embeddings.MistralAIEmbeddings") as mock_embeddings,
        pytest.raises(ValueError, match="SSRF Protection"),
    ):
        component.build_embeddings()

    mock_embeddings.assert_not_called()


def test_mistral_embeddings_default_endpoint_passes_no_client():
    pytest.importorskip("langchain_mistralai")
    from lfx_bundles.mistral.mistral_embeddings import MistralAIEmbeddingsComponent

    component = MistralAIEmbeddingsComponent(mistral_api_key="test")

    with patch("lfx_bundles.mistral.mistral_embeddings.MistralAIEmbeddings") as mock_embeddings:
        component.build_embeddings()

    mock_embeddings.assert_called_once()
    assert "client" not in mock_embeddings.call_args.kwargs
    assert "async_client" not in mock_embeddings.call_args.kwargs


def test_sambanova_build_blocks_metadata_url_before_sdk_client():
    pytest.importorskip("langchain_sambanova")
    from lfx_bundles.sambanova.sambanova import SambaNovaComponent

    component = SambaNovaComponent(base_url=BLOCKED_URL, model_name="model", api_key="test")

    with (
        patch("lfx_bundles.sambanova.sambanova.ChatSambaNovaCloud") as mock_chat,
        pytest.raises(ValueError, match="SSRF Protection"),
    ):
        component.build_model()

    mock_chat.assert_not_called()


def test_baidu_qianfan_build_blocks_metadata_url_before_sdk_client():
    """A metadata URL in Qianfan's "endpoint" is still refused before the SDK is built.

    The message changed with the guard: this field is a model identifier the SDK
    appends to its own API host, not a base URL, so it is rejected for being the
    wrong shape rather than by the base-URL SSRF policy. The property under test
    is unchanged - the URL never reaches QianfanChatEndpoint.
    """
    pytest.importorskip("qianfan")
    try:
        from lfx_bundles.baidu.baidu_qianfan_chat import QianfanChatEndpointComponent
    except Exception:
        pytest.skip("qianfan stack is not importable (likely pydantic v1 incompatibility)")

    component = QianfanChatEndpointComponent(
        endpoint=BLOCKED_URL, model="ERNIE-Bot-turbo-AI", qianfan_ak="ak", qianfan_sk="sk"
    )

    with (
        patch("lfx_bundles.baidu.baidu_qianfan_chat.QianfanChatEndpoint") as mock_qianfan,
        pytest.raises(ValueError, match="model identifier"),
    ):
        component.build_model()

    mock_qianfan.assert_not_called()


def test_mistral_embeddings_custom_endpoint_client_satisfies_the_sdk_contract():
    """An injected client must arrive fully formed, not transport-only.

    MistralAIEmbeddings only configures its clients inside ``if not self.client:``,
    and that branch is what sets base_url, the bearer header and the timeout. It
    then posts to the *relative* path "/embeddings", so a transport-only client
    has no base URL (httpx raises UnsupportedProtocol) and no credentials.
    """
    import httpx

    pytest.importorskip("langchain_mistralai")
    from lfx_bundles.mistral.mistral_embeddings import MistralAIEmbeddingsComponent

    component = MistralAIEmbeddingsComponent(
        endpoint="https://mistral.example.com/v1",
        mistral_api_key="sk-test",  # pragma: allowlist secret
        model="mistral-embed",
        max_concurrent_requests=1,
        max_retries=1,
        timeout=30,
    )
    # Pinning itself is exercised elsewhere; here we only need the non-default path,
    # so stand in kwargs that require no DNS resolution.
    with patch(
        "lfx_bundles.mistral.mistral_embeddings.provider_httpx_client_kwargs",
        return_value=({"follow_redirects": False}, {"follow_redirects": False}),
    ):
        embeddings = component.build_embeddings()

    client = embeddings.client
    assert str(client.base_url) == "https://mistral.example.com/v1/"
    assert client.headers["authorization"] == "Bearer sk-test"
    assert client.headers["content-type"] == "application/json"
    assert client.timeout.connect == 30
    assert client.follow_redirects is False
    assert str(embeddings.async_client.base_url) == "https://mistral.example.com/v1/"
    assert embeddings.async_client.headers["authorization"] == "Bearer sk-test"

    # And the request the SDK actually issues resolves and parses.
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"data": [{"embedding": [0.1, 0.2]}]})

    embeddings.client = httpx.Client(
        base_url=client.base_url,
        headers=client.headers,
        timeout=client.timeout,
        transport=httpx.MockTransport(handler),
    )
    assert embeddings.embed_documents(["hello"]) == [[0.1, 0.2]]
    assert seen["url"] == "https://mistral.example.com/v1/embeddings"
    assert seen["auth"] == "Bearer sk-test"


@pytest.mark.parametrize(
    "endpoint",
    ["ernie-3.5-8k-0329", "ernie-4.0-8k", "completions_pro", "ERNIE_Speed", ""],
)
def test_baidu_qianfan_accepts_model_identifiers(endpoint):
    """Qianfan's "endpoint" is a model id appended to the SDK's own host, not a URL.

    Validating it as an HTTP base URL rejected every legitimate value.
    """
    pytest.importorskip("qianfan")
    try:
        from lfx_bundles.baidu.baidu_qianfan_chat import QianfanChatEndpointComponent
    except Exception:
        pytest.skip("qianfan stack is not importable (likely pydantic v1 incompatibility)")

    component = QianfanChatEndpointComponent(
        endpoint=endpoint, model="ERNIE-Bot-turbo-AI", qianfan_ak="ak", qianfan_sk="sk"
    )
    with patch("lfx_bundles.baidu.baidu_qianfan_chat.QianfanChatEndpoint") as mock_qianfan:
        component.build_model()
    mock_qianfan.assert_called_once()


@pytest.mark.parametrize(
    "endpoint",
    [
        BLOCKED_URL,
        "https://evil.example.com",
        "//evil.example.com/x",
        "../../etc/passwd",
        "chat/completions",
        "model?x=1",
    ],
)
def test_baidu_qianfan_rejects_origin_and_path_injection(endpoint):
    """A value that changes the origin or escapes the SDK's path is still refused."""
    pytest.importorskip("qianfan")
    try:
        from lfx_bundles.baidu.baidu_qianfan_chat import QianfanChatEndpointComponent
    except Exception:
        pytest.skip("qianfan stack is not importable (likely pydantic v1 incompatibility)")

    component = QianfanChatEndpointComponent(
        endpoint=endpoint, model="ERNIE-Bot-turbo-AI", qianfan_ak="ak", qianfan_sk="sk"
    )
    with (
        patch("lfx_bundles.baidu.baidu_qianfan_chat.QianfanChatEndpoint") as mock_qianfan,
        pytest.raises(ValueError, match="model identifier"),
    ):
        component.build_model()
    mock_qianfan.assert_not_called()
