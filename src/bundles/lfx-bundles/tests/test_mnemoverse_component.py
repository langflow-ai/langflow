"""Unit tests for MnemoverseMemoryComponent."""

import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

pytest.importorskip("lfx_bundles")

from lfx.schema.data import Data
from lfx_bundles.mnemoverse.mnemoverse_chat_memory import MnemoverseMemoryComponent

FAKE_KEY = "not-a-real-mnemoverse-key"  # pragma: allowlist secret


def _read_response():
    return SimpleNamespace(
        items=[
            SimpleNamespace(
                atom_id="7f0c4f0e-0000-0000-0000-000000000001",
                content="The staging seed script must run before the integration suite.",
                relevance=0.91,
                domain="project:demo",
                metadata={"source": "chat"},
            ),
            SimpleNamespace(
                atom_id="7f0c4f0e-0000-0000-0000-000000000002",
                content="Rate limiting is per API token, not per IP.",
                relevance=0.52,
                domain="project:demo",
                metadata={},
            ),
        ]
    )


@pytest.mark.unit
class TestMnemoverseMemoryComponent:
    """Test the Mnemoverse Chat Memory component with a mocked client."""

    def test_memory_handle_type_is_provider_specific(self):
        """The client handle must not share the generic Memory type of Message History and Store Message."""
        node = MnemoverseMemoryComponent().to_frontend_node()["data"]["node"]
        assert node["template"]["existing_memory"]["input_types"] == ["MnemoverseMemory"]
        memory_output = next(output for output in node["outputs"] if output["name"] == "memory")
        assert "Memory" not in memory_output["types"]

    def test_build_requires_api_key_even_if_env_is_set(self, monkeypatch):
        """The SDK reads MNEMOVERSE_API_KEY when no key is passed; the component must not rely on it."""
        monkeypatch.setenv("MNEMOVERSE_API_KEY", FAKE_KEY)
        mock_sdk = Mock()
        with patch.dict(sys.modules, {"mnemoverse": mock_sdk}):
            component = MnemoverseMemoryComponent()
            with pytest.raises(ValueError, match="API key is required"):
                component.build_mnemoverse()
        mock_sdk.MnemoClient.assert_not_called()

    def test_build_passes_explicit_key(self):
        mock_sdk = Mock()
        with patch.dict(sys.modules, {"mnemoverse": mock_sdk}):
            component = MnemoverseMemoryComponent()
            component.mnemoverse_api_key = FAKE_KEY
            component.build_mnemoverse()
        mock_sdk.MnemoClient.assert_called_once_with(api_key=FAKE_KEY)

    def test_ingest_writes_with_domain_and_metadata(self):
        client = Mock()
        component = MnemoverseMemoryComponent()
        component.existing_memory = client
        component.ingest_message = "Prefers short answers."
        component.domain = "user:42"
        component.metadata = {"source": "chat"}

        assert component.ingest_data() is client
        client.write.assert_called_once_with("Prefers short answers.", domain="user:42", metadata={"source": "chat"})

    def test_ingest_without_message_does_not_write(self):
        client = Mock()
        component = MnemoverseMemoryComponent()
        component.existing_memory = client
        component.ingest_message = ""

        assert component.ingest_data() is client
        client.write.assert_not_called()

    def test_ingest_without_domain_omits_domain(self):
        client = Mock()
        component = MnemoverseMemoryComponent()
        component.existing_memory = client
        component.ingest_message = "Remember this."
        component.domain = ""
        component.metadata = {}

        component.ingest_data()
        client.write.assert_called_once_with("Remember this.")

    def test_search_maps_results(self):
        client = Mock()
        client.read.return_value = _read_response()
        component = MnemoverseMemoryComponent()
        component.existing_memory = client
        component.ingest_message = ""
        component.search_query = "what should I watch out for in CI?"
        component.domain = "project:demo"
        component.top_k = 5
        component.min_relevance = 0.4

        result = component.build_search_results()

        client.read.assert_called_once_with(
            "what should I watch out for in CI?", top_k=5, min_relevance=0.4, domain="project:demo"
        )
        assert isinstance(result, Data)
        assert [r["memory"] for r in result.data["results"]] == [
            "The staging seed script must run before the integration suite.",
            "Rate limiting is per API token, not per IP.",
        ]
        assert result.data["results"][0]["id"] == "7f0c4f0e-0000-0000-0000-000000000001"
        assert result.data["results"][0]["relevance"] == 0.91

    def test_search_without_query_returns_empty(self):
        client = Mock()
        component = MnemoverseMemoryComponent()
        component.existing_memory = client
        component.ingest_message = ""
        component.search_query = ""

        result = component.build_search_results()

        assert result.data == {"results": []}
        client.read.assert_not_called()

    def test_errors_from_the_client_propagate(self):
        client = Mock()
        client.read.side_effect = RuntimeError("boom")
        component = MnemoverseMemoryComponent()
        component.existing_memory = client
        component.ingest_message = ""
        component.search_query = "anything"
        component.top_k = 10
        component.min_relevance = 0.3
        component.domain = ""

        with pytest.raises(RuntimeError, match="boom"):
            component.build_search_results()

    def test_client_is_closed_after_each_call(self):
        """Inside a running loop an unclosed MnemoClient keeps a daemon thread alive; each call must close it."""
        client = Mock()
        client.read.return_value = _read_response()
        component = MnemoverseMemoryComponent()
        component.existing_memory = client
        component.ingest_message = "Remember this."
        component.search_query = "anything"
        component.domain = ""
        component.metadata = {}
        component.top_k = 10
        component.min_relevance = 0.3

        component.build_search_results()

        assert client.write.call_count == 1
        assert client.read.call_count == 1
        assert client.close.call_count == 2

    def test_client_is_closed_when_the_call_fails(self):
        client = Mock()
        client.write.side_effect = RuntimeError("boom")
        component = MnemoverseMemoryComponent()
        component.existing_memory = client
        component.ingest_message = "Remember this."
        component.domain = ""
        component.metadata = {}

        with pytest.raises(RuntimeError, match="boom"):
            component.ingest_data()
        client.close.assert_called_once_with()

    async def test_one_build_stores_the_message_once(self):
        """Building both outputs must not store the message twice."""
        client = Mock()
        client.read.return_value = _read_response()
        component = MnemoverseMemoryComponent()
        component.existing_memory = client
        component.ingest_message = "Remember this."
        component.search_query = "anything"
        component.domain = ""
        component.metadata = {}
        component.top_k = 10
        component.min_relevance = 0.3

        await component._build_results()

        assert client.write.call_count == 1
        assert client.read.call_count == 1
