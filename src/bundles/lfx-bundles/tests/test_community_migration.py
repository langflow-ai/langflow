"""Exercise the existing component contracts through their replacement SDKs."""

from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding
from lfx.schema.data import Data
from lfx_bundles.apify.apify_actor import ApifyActorsComponent
from lfx_bundles.chroma.chroma import ChromaVectorStoreComponent
from lfx_bundles.cloudflare.cloudflare import CloudflareWorkersAIEmbeddingsComponent
from lfx_bundles.needle.needle import NeedleComponent
from requests import HTTPError, Response

TEST_TOKEN = "test-token"  # noqa: S105 - dummy credential for HTTP fixtures


@pytest.mark.parametrize("fields", [None, ["nested.title", "missing"]])
def test_apify_uses_authenticated_client_for_clean_dataset(fields):
    component = ApifyActorsComponent()
    client = MagicMock()
    client.actor.return_value.call.return_value = {"id": "run-id"}
    client.run.return_value.log.return_value.stream.return_value = nullcontext(None)
    items = [{"nested": {"title": "A"}, "url": "https://example.org"}]
    client.dataset.return_value.list_items.return_value.items = items
    with (
        patch.object(component, "_get_apify_client", return_value=client),
        patch.object(component, "_get_run_dataset_id", return_value="dataset-id"),
    ):
        result = component.run_actor("actor", {"query": "test"}, fields)
    client.actor.return_value.call.assert_called_once_with(run_input={"query": "test"}, wait_secs=1)
    client.run.return_value.wait_for_finish.assert_called_once_with()
    client.dataset.assert_called_once_with("dataset-id")
    client.dataset.return_value.list_items.assert_called_once_with(clean=True)
    assert result == (items if fields is None else [{"nested_title": "A", "missing": None}])


@pytest.mark.parametrize(
    ("query", "expected_k"),
    [
        ("question", 20),
        ({"query": "question", "top_k": 2}, 20),
        ({"query": "question", "top_k": "35"}, 35),
        ({"query": "question", "top_k": "bad"}, 20),
    ],
)
def test_needle_query_and_output_contract(query, expected_k):
    component = NeedleComponent().set(needle_api_key="test-key", collection_id="collection", top_k=20)
    component.query = query
    client = MagicMock()
    client.collections.search.return_value = [SimpleNamespace(content="Result", metadata={"new": "not exposed"})]
    with patch("needle.v1.NeedleClient", return_value=client) as constructor:
        result = component.run()
    constructor.assert_called_once_with(api_key="test-key")  # pragma: allowlist secret
    client.collections.search.assert_called_once_with(collection_id="collection", text="question", top_k=expected_k)
    assert result.text == "Question: question\n\nContext:\nDocument 1:\nResult"
    assert result.data["additional_kwargs"] == {
        "source_documents": [{"page_content": "Result", "metadata": {}}],
        "top_k_used": expected_k,
    }


def test_needle_empty_and_failed_search():
    component = NeedleComponent().set(needle_api_key="test-key", collection_id="collection", query="question")
    with patch("needle.v1.NeedleClient") as constructor:
        constructor.return_value.collections.search.return_value = []
        assert component.run().text == "No relevant documents found for the query."
        constructor.return_value.collections.search.side_effect = RuntimeError("unavailable")
        with pytest.raises(ValueError, match="Error processing query: unavailable"):
            component.run()
    component.query = " "
    with pytest.raises(ValueError, match="query cannot be empty"):
        component.run()


def test_cloudflare_batching_and_existing_routing(monkeypatch):
    monkeypatch.setenv("AI_GATEWAY", "unrelated-gateway")
    embeddings = (
        CloudflareWorkersAIEmbeddingsComponent()
        .set(account_id="account", api_token=TEST_TOKEN, batch_size=2)
        .build_embeddings()
    )
    observed = []

    def post(url, *, headers, json):
        observed.append((url, headers, json))
        response = Response()
        response.status_code = 200
        response._content = __import__("json").dumps({"result": {"data": [[1.0, 2.0] for _ in json["text"]]}}).encode()
        return response

    with patch("langchain_cloudflare.embeddings.requests.post", side_effect=post):
        assert embeddings.embed_documents(["a\nb", "c", "d"]) == [[1.0, 2.0]] * 3
    assert [call[2]["text"] for call in observed] == [["a b", "c"], ["d"]]
    assert observed[0][0] == "https://api.cloudflare.com/client/v4/accounts/account/ai/run/@cf/baai/bge-base-en-v1.5"
    assert observed[0][1] == {"Authorization": "Bearer test-token"}


def test_cloudflare_rejects_http_errors():
    embeddings = (
        CloudflareWorkersAIEmbeddingsComponent().set(account_id="account", api_token=TEST_TOKEN).build_embeddings()
    )
    response = Response()
    response.status_code = 401
    response._content = b'{"error": "unauthorized"}'
    with patch("langchain_cloudflare.embeddings.requests.post", return_value=response), pytest.raises(HTTPError):
        embeddings.embed_query("test")


def test_cloudflare_embeddings_remain_picklable():
    # The Redis cache serializes built vertex results; the retired Community class pickled.
    import pickle

    embeddings = (
        CloudflareWorkersAIEmbeddingsComponent().set(account_id="account", api_token=TEST_TOKEN).build_embeddings()
    )
    restored = pickle.loads(pickle.dumps(embeddings))  # noqa: S301 - round-trips an object built in this test
    assert type(restored) is type(embeddings)
    assert restored.headers == {"Authorization": "Bearer test-token"}
    assert restored._inference_url == embeddings._inference_url


def test_chroma_persists_filtered_metadata_without_community(tmp_path):
    component = ChromaVectorStoreComponent().set(
        collection_name="migration-test",
        persist_directory=str(tmp_path),
        embedding=DeterministicFakeEmbedding(size=8),
        allow_duplicates=True,
        ingest_data=[
            Data(
                data={
                    "text": "document",
                    "str": "value",
                    "bool": False,
                    "int": 0,
                    "float": 1.5,
                    "none": None,
                    "list": [],
                    "dict": {},
                }
            )
        ],
    )
    with patch.dict("sys.modules", {"langchain_community.vectorstores.utils": None}):
        store = component.build_vector_store()
    result = store.get()
    assert result["documents"] == ["document"]
    assert result["metadatas"] == [{"str": "value", "bool": False, "int": 0, "float": 1.5}]


@pytest.mark.asyncio
async def test_cloudflare_async_preserves_slow_successful_responses():
    import asyncio
    import json
    import threading
    import time
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class EmbeddingHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            # Exceeds the dedicated provider's default async client's five-second timeout.
            time.sleep(5.2)
            body = json.dumps({"result": {"data": [[1.0, 2.0] for _ in request["text"]]}}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), EmbeddingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        embeddings = (
            CloudflareWorkersAIEmbeddingsComponent()
            .set(
                account_id="account",
                api_token=TEST_TOKEN,
                api_base_url=f"http://127.0.0.1:{server.server_port}",
            )
            .build_embeddings()
        )
        query, documents = await asyncio.wait_for(
            asyncio.gather(embeddings.aembed_query("question"), embeddings.aembed_documents(["a", "b"])),
            timeout=15,
        )
        assert query == [1.0, 2.0]
        assert documents == [[1.0, 2.0], [1.0, 2.0]]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
