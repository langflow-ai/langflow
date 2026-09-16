"""Exercise the Cohere component surface after removing its indirect Community edge."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from langchain_core.documents import Document
from lfx_cohere.components.cohere.cohere_embeddings import CohereEmbeddingsComponent
from lfx_cohere.components.cohere.cohere_models import CohereComponent
from lfx_cohere.components.cohere.cohere_rerank import CohereRerankComponent

TEST_KEY = "test-key"


def test_chat_constructor_preserves_temperature_and_credentials():
    response = SimpleNamespace(models=[SimpleNamespace(name="command-r-plus")])
    with patch("cohere.models.client.ModelsClient.list", return_value=response) as discover:
        model = CohereComponent().set(cohere_api_key=TEST_KEY, temperature=0.2).build_model()
    discover.assert_called_once_with(default_only=True, endpoint="chat")
    assert model.model == "command-r-plus"
    assert model.temperature == 0.2
    assert model.cohere_api_key.get_secret_value() == TEST_KEY


def test_embeddings_preserve_request_and_result_contract():
    embeddings = CohereEmbeddingsComponent().set(api_key=TEST_KEY, model_name="embed-english-v3.0").build_embeddings()
    response = MagicMock()
    response.dict.return_value = {"embeddings": {"float": [[0.1, 0.2]]}}
    with patch.object(embeddings.client, "embed", return_value=response) as embed:
        assert embeddings.embed_query("question") == [0.1, 0.2]
    assert embed.call_args.kwargs["texts"] == ["question"]
    assert embed.call_args.kwargs["model"] == "embed-english-v3.0"
    assert embed.call_args.kwargs["input_type"] == "search_query"


def test_reranker_preserves_order_and_metadata():
    compressor = CohereRerankComponent().set(api_key=TEST_KEY, top_n=1).build_compressor()
    documents = [Document(page_content="first"), Document(page_content="second", metadata={"source": "saved"})]
    response = SimpleNamespace(results=[SimpleNamespace(index=1, relevance_score=0.9)])
    with patch.object(compressor.client, "rerank", return_value=response) as rerank:
        result = compressor.compress_documents(documents, "question")
    assert rerank.call_args.kwargs["top_n"] == 1
    assert result[0].page_content == "second"
    assert result[0].metadata == {"source": "saved", "relevance_score": 0.9}
    assert documents[1].metadata == {"source": "saved"}
