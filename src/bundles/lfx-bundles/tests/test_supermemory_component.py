"""Unit tests for SupermemoryMemoryComponent."""

import json
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx
import pytest

pytest.importorskip("lfx_bundles")

from lfx.schema.data import Data
from lfx_bundles.supermemory.supermemory_chat_memory import SupermemoryMemoryComponent

FAKE_KEY = "not-a-real-supermemory-key"  # pragma: allowlist secret


def _search_response():
    return SimpleNamespace(
        results=[
            SimpleNamespace(
                id="mem_1",
                memory="Alex prefers morning meetings.",
                chunk=None,
                similarity=0.91,
                metadata={"source": "chat"},
            ),
            SimpleNamespace(
                id="chunk_1",
                memory=None,
                chunk="Let's meet at 9am.",
                similarity=0.52,
                metadata={},
            ),
        ]
    )


def _profile_response():
    return SimpleNamespace(
        profile=SimpleNamespace(
            static=[SimpleNamespace(id="mem_1", memory="Alex is a product manager.")],
            dynamic=[SimpleNamespace(id="mem_2", memory="Alex is planning a launch.")],
            buckets={"preferences": [SimpleNamespace(id="mem_3", memory="Alex prefers morning meetings.")]},
        )
    )


@pytest.mark.unit
class TestSupermemoryMemoryComponent:
    """Test the Supermemory Chat Memory component with a mocked client."""

    def test_build_supermemory_requires_api_key(self, monkeypatch):
        """build_supermemory fails before reaching the SDK when no API key is provided.

        The SDK reads SUPERMEMORY_API_KEY when no key is passed. The component must not
        rely on that fallback, so a key set in the server environment is never used for
        a flow that did not provide one.
        """
        monkeypatch.setenv("SUPERMEMORY_API_KEY", FAKE_KEY)
        mock_sdk = Mock()
        with patch.dict(sys.modules, {"supermemory": mock_sdk}):
            component = SupermemoryMemoryComponent()

            with pytest.raises(ValueError, match="API key is required"):
                component.build_supermemory()

        mock_sdk.Supermemory.assert_not_called()

    def test_build_supermemory_passes_api_key_to_client(self):
        """The API key flows to the SDK client constructor."""
        mock_sdk = Mock()
        with patch.dict(sys.modules, {"supermemory": mock_sdk}):
            component = SupermemoryMemoryComponent(supermemory_api_key=FAKE_KEY)
            client = component.build_supermemory()

        mock_sdk.Supermemory.assert_called_once_with(api_key=FAKE_KEY)
        assert client is mock_sdk.Supermemory.return_value

    def test_build_supermemory_reports_missing_sdk(self):
        """A missing SDK surfaces an actionable install hint."""
        with patch.dict(sys.modules, {"supermemory": None}):
            component = SupermemoryMemoryComponent(supermemory_api_key=FAKE_KEY)

            with pytest.raises(ImportError, match="pip install"):
                component.build_supermemory()

    def test_ingest_data_adds_message_to_namespace(self):
        """Ingestion scopes the document to the namespace and forwards id and metadata."""
        memory = Mock()
        component = SupermemoryMemoryComponent().set(
            existing_memory=memory,
            namespace="user_alex",
            ingest_message="hello",
            document_id="session-1",
            metadata={"source": "chat"},
        )

        result = component.ingest_data()

        assert result is memory
        memory.add.assert_called_once_with("user_alex", content="hello", id="session-1", metadata={"source": "chat"})

    def test_ingest_data_omits_optional_arguments(self):
        """Without a document ID or metadata, only the content is sent."""
        memory = Mock()
        component = SupermemoryMemoryComponent().set(
            existing_memory=memory,
            namespace="user_alex",
            ingest_message="hello",
        )

        component.ingest_data()

        memory.add.assert_called_once_with("user_alex", content="hello")

    @pytest.mark.parametrize(
        "inputs",
        [
            {"namespace": "user_alex"},
            {"ingest_message": "hello"},
        ],
    )
    def test_ingest_data_skips_when_message_or_namespace_is_missing(self, inputs):
        """Nothing is ingested unless both the message and the namespace are set."""
        memory = Mock()
        component = SupermemoryMemoryComponent().set(existing_memory=memory, **inputs)

        result = component.ingest_data()

        assert result is memory
        memory.add.assert_not_called()

    def test_build_search_results_searches_namespace(self):
        """Search is scoped to the namespace and returns the results as Data."""
        memory = Mock()
        memory.search.return_value = _search_response()
        component = SupermemoryMemoryComponent().set(
            existing_memory=memory,
            namespace="user_alex",
            search_query="when does alex like to meet?",
            search_limit=5,
            search_mode="memories",
            threshold=0.5,
        )

        result = component.build_search_results()

        memory.add.assert_not_called()
        memory.search.assert_called_once_with(
            "user_alex",
            query="when does alex like to meet?",
            limit=5,
            search_mode="memories",
            threshold=0.5,
        )
        assert isinstance(result, Data)
        assert result.data == {
            "results": [
                {
                    "id": "mem_1",
                    "memory": "Alex prefers morning meetings.",
                    "chunk": None,
                    "similarity": 0.91,
                    "metadata": {"source": "chat"},
                },
                {
                    "id": "chunk_1",
                    "memory": None,
                    "chunk": "Let's meet at 9am.",
                    "similarity": 0.52,
                    "metadata": {},
                },
            ]
        }

    def test_build_search_results_uses_default_search_options(self):
        """The default search options match the Supermemory API defaults."""
        memory = Mock()
        memory.search.return_value = SimpleNamespace(results=[])
        component = SupermemoryMemoryComponent().set(
            existing_memory=memory,
            namespace="user_alex",
            ingest_message="hello",
            search_query="x",
        )

        result = component.build_search_results()

        memory.add.assert_called_once_with("user_alex", content="hello")
        memory.search.assert_called_once_with("user_alex", query="x", limit=10, search_mode="hybrid", threshold=0.3)
        assert result.data == {"results": []}

    def test_build_search_results_without_query_returns_no_results(self):
        """Without a search query, no search request is made."""
        memory = Mock()
        component = SupermemoryMemoryComponent().set(existing_memory=memory, namespace="user_alex")

        result = component.build_search_results()

        memory.search.assert_not_called()
        assert result.data == {"results": []}

    def test_build_profile_returns_profile_facts(self):
        """The profile output returns static facts, dynamic context, and buckets."""
        memory = Mock()
        memory.profile.return_value = _profile_response()
        component = SupermemoryMemoryComponent().set(existing_memory=memory, namespace="user_alex")

        result = component.build_profile()

        memory.profile.assert_called_once_with("user_alex")
        assert result.data == {
            "static": [{"id": "mem_1", "memory": "Alex is a product manager."}],
            "dynamic": [{"id": "mem_2", "memory": "Alex is planning a launch."}],
            "buckets": {"preferences": [{"id": "mem_3", "memory": "Alex prefers morning meetings."}]},
        }

    def test_build_profile_without_namespace_returns_empty_profile(self):
        """Without a namespace, no profile request is made."""
        memory = Mock()
        component = SupermemoryMemoryComponent().set(existing_memory=memory)

        result = component.build_profile()

        memory.profile.assert_not_called()
        assert result.data == {"static": [], "dynamic": [], "buckets": {}}

    def test_component_requests_match_the_installed_sdk(self):
        """With the real SDK on a mocked HTTP transport, requests and parsed responses line up."""
        supermemory = pytest.importorskip("supermemory")
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append((request.url.path, json.loads(request.content)))
            if request.url.path.endswith("/search"):
                result = {
                    "id": "mem_1",
                    "memory": "Alex prefers morning meetings.",
                    "metadata": {},
                    "similarity": 0.91,
                    "isLatest": True,
                    "isInference": False,
                    "system": {},
                }
                return httpx.Response(200, json={"results": [result], "searchTime": 12.0})
            if request.url.path.endswith("/profile"):
                fact = {"id": "mem_1", "memory": "Alex is a product manager."}
                return httpx.Response(200, json={"profile": {"static": [fact], "dynamic": [], "buckets": {}}})
            return httpx.Response(200, json={"id": "session-1", "status": "queued"})

        client = supermemory.Supermemory(
            api_key=FAKE_KEY,
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        component = SupermemoryMemoryComponent().set(
            existing_memory=client,
            namespace="user_alex",
            ingest_message="hello",
            document_id="session-1",
            search_query="when does alex like to meet?",
        )

        search_results = component.build_search_results()
        profile = component.build_profile()

        assert requests == [
            ("/ns/user_alex/document", {"content": "hello", "id": "session-1"}),
            (
                "/ns/user_alex/search",
                {"query": "when does alex like to meet?", "searchMode": "hybrid", "limit": 10, "threshold": 0.3},
            ),
            ("/ns/user_alex/profile", {}),
        ]
        assert search_results.data["results"] == [
            {
                "id": "mem_1",
                "memory": "Alex prefers morning meetings.",
                "chunk": None,
                "similarity": 0.91,
                "metadata": {},
            }
        ]
        assert profile.data == {
            "static": [{"id": "mem_1", "memory": "Alex is a product manager."}],
            "dynamic": [],
            "buckets": {},
        }
