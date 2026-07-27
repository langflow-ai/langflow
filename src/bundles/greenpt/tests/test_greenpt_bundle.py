from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
from langchain_core.documents import Document
from lfx_greenpt import GreenPTRerankComponent, GreenPTSpeechToTextComponent, discovery
from lfx_greenpt.components.greenpt.rerank import GreenPTReranker
from lfx_greenpt.models import GREENPT_BASE_URL, ChatGreenPT, GreenPTEmbeddings
from pydantic import SecretStr


def _ok_response(payload: object) -> MagicMock:
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


def test_bundle_registers_provider_and_components_end_to_end():
    from lfx.base.models import provider_registry
    from lfx.extension import load_extension

    provider_registry.clear()
    try:
        root = Path(__file__).resolve().parents[1] / "src" / "lfx_greenpt"
        result = load_extension(root)
        assert result.ok, (result.errors, result.warnings)
        assert provider_registry.is_registered("GreenPT")
        assert provider_registry.live_discovery_for("GreenPT") is not None
        assert provider_registry.validator_for("GreenPT") is not None
        assert {component.class_name for component in result.components} == {
            "GreenPTRerankComponent",
            "GreenPTSpeechToTextComponent",
        }
    finally:
        provider_registry.clear()


def test_discovery_prioritizes_flagship_models_for_each_type():
    response = _ok_response(
        {
            "data": [
                {"id": "other-chat"},
                {"id": "green-embedding"},
                {"id": "kimi-k2.7-code"},
                {"id": "green-rerank"},
                {"id": "GreenS Pro"},
                {"id": "glm-5.2"},
            ]
        }
    )
    with (
        patch.object(discovery, "get_provider_variable_value", return_value="secret"),
        patch.object(discovery, "ssrf_safe_httpx_get", return_value=response) as mock_get,
    ):
        language_models = discovery.fetch_live_greenpt_models("user", "llm")
        embedding_models = discovery.fetch_live_greenpt_models("user", "embeddings")

    expected = ["glm-5.2", "kimi-k2.7-code", "GreenS Pro", "green-embedding", "green-rerank", "other-chat"]
    assert [model["name"] for model in language_models] == expected
    assert [model["name"] for model in embedding_models] == expected
    assert all(model["tool_calling"] for model in language_models)
    assert all(not model["tool_calling"] for model in embedding_models)
    assert mock_get.call_args.kwargs["headers"] == {"Authorization": "Bearer secret"}
    assert mock_get.call_args.kwargs["follow_redirects"] is False


def test_discovery_degrades_to_empty_without_credentials():
    with patch.object(discovery, "get_provider_variable_value", return_value=None):
        assert discovery.fetch_live_greenpt_models("user") == []


def test_credential_validator_reports_authentication_failure():
    response = MagicMock(status_code=401)
    with (
        patch.object(discovery, "ssrf_safe_httpx_get", return_value=response),
        pytest.raises(ValueError, match="authentication failed"),
    ):
        discovery.validate_greenpt_credentials("GreenPT", {"GREENPT_API_KEY": "bad"})


def test_model_classes_force_greenpt_endpoint():
    chat = ChatGreenPT(model="glm-5.2", api_key="test-key")  # pragma: allowlist secret
    embeddings = GreenPTEmbeddings(model="green-embedding", api_key="test-key")  # pragma: allowlist secret

    assert str(chat.openai_api_base).rstrip("/") == GREENPT_BASE_URL
    assert str(embeddings.openai_api_base).rstrip("/") == GREENPT_BASE_URL


def test_reranker_shapes_request_and_does_not_mutate_documents():
    documents = [
        Document(page_content="alpha", metadata={"source": "a"}),
        Document(page_content="beta", metadata={"source": "b"}),
    ]
    response = _ok_response({"results": [{"index": 1, "relevance_score": 0.9}]})
    reranker = GreenPTReranker(api_key=SecretStr("secret"), top_n=1)

    with patch("lfx_greenpt.components.greenpt.rerank.httpx.post", return_value=response) as mock_post:
        result = reranker.compress_documents(documents, "query")

    assert result == [Document(page_content="beta", metadata={"source": "b", "relevance_score": 0.9})]
    assert documents[1].metadata == {"source": "b"}
    assert mock_post.call_args.kwargs["json"] == {
        "model": "green-rerank",
        "query": "query",
        "documents": ["alpha", "beta"],
        "top_n": 1,
    }
    assert mock_post.call_args.kwargs["headers"] == {"Authorization": "Bearer secret"}


def test_reranker_rejects_invalid_document_index():
    reranker = GreenPTReranker(api_key=SecretStr("secret"))
    response = _ok_response({"results": [{"index": 5, "relevance_score": 0.9}]})

    with (
        patch("lfx_greenpt.components.greenpt.rerank.httpx.post", return_value=response),
        pytest.raises(ValueError, match="invalid document index"),
    ):
        reranker.compress_documents([Document(page_content="alpha")], "query")


@pytest.mark.parametrize("field", [{"index": True, "relevance_score": 0.9}, {"index": 0, "relevance_score": False}])
def test_reranker_rejects_boolean_numeric_fields(field: dict):
    reranker = GreenPTReranker(api_key=SecretStr("secret"))
    response = _ok_response({"results": [field]})

    with (
        patch("lfx_greenpt.components.greenpt.rerank.httpx.post", return_value=response),
        pytest.raises(TypeError, match=r"invalid rerank result|without a relevance score"),
    ):
        reranker.compress_documents([Document(page_content="alpha")], "query")


def test_component_builds_reranker():
    component = GreenPTRerankComponent()
    component.set_attributes({"api_key": "secret", "model": "green-rerank", "top_n": 2})

    compressor = component.build_compressor()

    assert isinstance(compressor, GreenPTReranker)
    assert compressor.top_n == 2


def test_speech_to_text_shapes_request_and_extracts_transcript():
    component = GreenPTSpeechToTextComponent()
    component.set_attributes(
        {
            "api_key": "secret",
            "audio_url": "https://cdn.example.com/audio.mp3",
            "model": "green-s-pro",
            "language": "en",
            "punctuate": True,
            "smart_format": True,
        }
    )
    response = _ok_response({"results": {"channels": [{"alternatives": [{"transcript": "Hello world."}]}]}})

    with patch("lfx_greenpt.components.greenpt.transcribe.httpx.post", return_value=response) as mock_post:
        message = component.transcribe()

    assert message.text == "Hello world."
    assert mock_post.call_args.kwargs["headers"] == {"Authorization": "Token secret"}
    assert mock_post.call_args.kwargs["json"] == {"url": "https://cdn.example.com/audio.mp3"}
    assert mock_post.call_args.kwargs["params"] == {
        "model": "green-s-pro",
        "language": "en",
        "punctuate": True,
        "smart_format": True,
    }


@pytest.mark.parametrize(
    "url",
    ["file:///tmp/audio.mp3", "https://user:password@example.com/audio.mp3", "not-a-url"],
)
def test_speech_to_text_rejects_invalid_urls(url: str):
    component = GreenPTSpeechToTextComponent()
    component.set_attributes(
        {
            "api_key": "secret",
            "audio_url": url,
            "model": "green-s",
            "language": "",
            "punctuate": True,
            "smart_format": True,
        }
    )

    with pytest.raises(ValueError, match="public HTTP or HTTPS"):
        component.transcribe()


@pytest.mark.parametrize(
    "payload",
    [
        {"results": {}},
        {"results": {"channels": [{"alternatives": [{"transcript": "   "}]}]}},
    ],
)
def test_speech_to_text_rejects_malformed_response(payload: object):
    component = GreenPTSpeechToTextComponent()
    component.set_attributes(
        {
            "api_key": "secret",
            "audio_url": "https://cdn.example.com/audio.mp3",
            "model": "green-s",
            "language": "",
            "punctuate": True,
            "smart_format": True,
        }
    )
    with (
        patch(
            "lfx_greenpt.components.greenpt.transcribe.httpx.post",
            return_value=_ok_response(payload),
        ),
        pytest.raises((TypeError, ValueError), match="invalid speech-to-text"),
    ):
        component.transcribe()


def test_network_errors_remain_actionable():
    request = httpx.Request("POST", "https://api.greenpt.ai/v1/rerank")
    response = httpx.Response(503, request=request)
    reranker = GreenPTReranker(api_key=SecretStr("secret"))
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "unavailable", request=request, response=response
    )

    with (
        patch("lfx_greenpt.components.greenpt.rerank.httpx.post", return_value=mock_response),
        pytest.raises(httpx.HTTPStatusError),
    ):
        reranker.compress_documents([Document(page_content="alpha")], "query")
