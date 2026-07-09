from unittest.mock import patch

from lfx.components.vllm.vllm_embeddings import VllmEmbeddingsComponent


def test_vllm_embeddings_disables_tiktoken_by_default() -> None:
    component = VllmEmbeddingsComponent().set(
        model_name="qwen-embedding",
        api_base="https://example.test/v1",
        api_key="test-key",
        dimensions=0,
        chunk_size=1000,
        max_retries=3,
        request_timeout="",
        show_progress_bar=False,
        skip_empty=False,
        model_kwargs={},
        default_headers={},
        default_query={},
    )

    with patch("lfx.components.vllm.vllm_embeddings.OpenAIEmbeddings") as embeddings:
        component.build_embeddings()

    embeddings.assert_called_once()
    assert embeddings.call_args.kwargs["tiktoken_enabled"] is False
    assert embeddings.call_args.kwargs["check_embedding_ctx_length"] is False


def test_vllm_embeddings_allows_tiktoken_when_enabled() -> None:
    component = VllmEmbeddingsComponent().set(
        model_name="qwen-embedding",
        api_base="https://example.test/v1",
        api_key="test-key",
        dimensions=0,
        chunk_size=1000,
        max_retries=3,
        request_timeout="",
        show_progress_bar=False,
        skip_empty=False,
        tiktoken_enable=True,
        model_kwargs={},
        default_headers={},
        default_query={},
    )

    with patch("lfx.components.vllm.vllm_embeddings.OpenAIEmbeddings") as embeddings:
        component.build_embeddings()

    embeddings.assert_called_once()
    assert embeddings.call_args.kwargs["tiktoken_enabled"] is True
    assert embeddings.call_args.kwargs["check_embedding_ctx_length"] is False
