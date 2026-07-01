"""Unit tests for Mem0MemoryComponent cloud validation."""

import os
from unittest.mock import Mock, patch

import pytest
from lfx.components.mem0.mem0_chat_memory import Mem0MemoryComponent


@pytest.mark.unit
class TestMem0CloudValidation:
    """Test Mem0 component cloud validation."""

    def test_mem0_telemetry_is_disabled_by_default(self):
        """Langflow should not start mem0's PostHog telemetry on component import."""
        from mem0.memory import telemetry as mem0_telemetry

        assert os.environ["MEM0_TELEMETRY"] == "False"
        assert mem0_telemetry.MEM0_TELEMETRY is False
        assert mem0_telemetry.client_telemetry.posthog is None

    def test_build_mem0_disabled_in_astra_cloud(self):
        """Test that build_mem0 raises an error when ASTRA_CLOUD_DISABLE_COMPONENT is true."""
        with patch.dict(os.environ, {"ASTRA_CLOUD_DISABLE_COMPONENT": "true"}):
            component = Mem0MemoryComponent(openai_api_key="test-key")

            with pytest.raises(ValueError, match=r".*") as exc_info:
                component.build_mem0()

            error_msg = str(exc_info.value).lower()
            assert "astra" in error_msg or "cloud" in error_msg

    @patch("lfx.components.mem0.mem0_chat_memory.Memory")
    def test_build_mem0_works_when_not_in_cloud(self, mock_memory):
        """build_mem0 works when not in cloud, passing the OpenAI key through mem0 config.

        The key must NOT be written to os.environ: that is process-global and persists
        across requests, so in a shared serving process (lfx serve) one caller's key
        would leak into other concurrent requests.
        """
        with patch.dict(os.environ, {"ASTRA_CLOUD_DISABLE_COMPONENT": "false"}):
            os.environ.pop("OPENAI_API_KEY", None)
            fake_key = "not-a-real-openai-key"
            component = Mem0MemoryComponent(openai_api_key=fake_key)
            component.build_mem0()

            # Key flows through config, not the environment.
            mock_memory.from_config.assert_called_once()
            config = mock_memory.from_config.call_args.kwargs["config_dict"]
            assert config["llm"]["config"]["api_key"] == fake_key
            assert config["embedder"]["config"]["api_key"] == fake_key
            # Regression guard for the credential-bleed bug: never pollute os.environ.
            assert "OPENAI_API_KEY" not in os.environ

    def test_build_search_results_uses_mem0_2_filters_for_search(self):
        """Test that search uses filters for Mem0 2.x entity scoping."""
        memory = Mock()
        memory.search.return_value = [{"memory": "hello"}]
        component = Mem0MemoryComponent(_user_id="u").set(
            existing_memory=memory,
            ingest_message="hello",
            search_query="x",
        )

        result = component.build_search_results()

        assert result == [{"memory": "hello"}]
        memory.add.assert_called_once_with("hello", user_id="u", metadata={})
        memory.search.assert_called_once_with(query="x", filters={"user_id": "u"})

    def test_build_search_results_uses_mem0_2_filters_for_get_all(self):
        """Test that get_all uses filters for Mem0 2.x entity scoping."""
        memory = Mock()
        memory.get_all.return_value = [{"memory": "hello"}]
        component = Mem0MemoryComponent(_user_id="u").set(
            existing_memory=memory,
            ingest_message="hello",
        )

        result = component.build_search_results()

        assert result == [{"memory": "hello"}]
        memory.add.assert_called_once_with("hello", user_id="u", metadata={})
        memory.get_all.assert_called_once_with(filters={"user_id": "u"})
