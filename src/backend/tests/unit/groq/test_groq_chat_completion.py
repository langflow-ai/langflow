"""Tests for Groq _test_chat_completion method."""

import sys
from unittest.mock import MagicMock, Mock, patch

import pytest
from lfx.base.models.groq_model_discovery import GroqModelDiscovery


class TestChatCompletionDetection:
    """Test _test_chat_completion method."""

    @patch("groq.Groq")
    def test_chat_completion_success(self, mock_groq, mock_api_key, mock_groq_client_tool_calling_success):
        """Test successful chat completion returns True."""
        mock_groq.return_value = mock_groq_client_tool_calling_success()

        discovery = GroqModelDiscovery(api_key=mock_api_key)
        result = discovery._test_chat_completion("llama-3.1-8b-instant")

        assert result is True

    @patch("groq.Groq")
    def test_chat_completion_not_supported(self, mock_groq, mock_api_key, mock_groq_client_chat_not_supported):
        """Test model that does not support chat completions returns False."""
        mock_groq.return_value = mock_groq_client_chat_not_supported()

        discovery = GroqModelDiscovery(api_key=mock_api_key)
        result = discovery._test_chat_completion("speech-model")

        assert result is False

    @patch("groq.Groq")
    def test_chat_completion_terms_required_returns_none(
        self, mock_groq, mock_api_key, mock_groq_client_chat_terms_required
    ):
        """Test that access/entitlement errors cause _test_chat_completion to return None."""
        mock_groq.return_value = mock_groq_client_chat_terms_required()

        discovery = GroqModelDiscovery(api_key=mock_api_key)
        result = discovery._test_chat_completion("gated-model")

        assert result is None

    @patch("groq.Groq")
    def test_chat_completion_transient_error_returns_none(self, mock_groq, mock_api_key, mock_groq_client_rate_limit):
        """Test that transient errors (e.g. rate limits) return None (indeterminate)."""
        mock_groq.return_value = mock_groq_client_rate_limit()

        discovery = GroqModelDiscovery(api_key=mock_api_key)
        result = discovery._test_chat_completion("llama-3.1-8b-instant")

        assert result is None

    def test_chat_completion_import_error_raises(self, mock_api_key):
        """Test that ImportError propagates when the groq package is not installed."""
        # Simulate groq not being installed by hiding it from sys.modules
        with patch.dict(sys.modules, {"groq": None}):
            discovery = GroqModelDiscovery(api_key=mock_api_key)
            with pytest.raises(ImportError):
                discovery._test_chat_completion("test-model")

    @patch("lfx.base.models.groq_model_discovery.requests.get")
    @patch("groq.Groq")
    def test_chat_failure_marks_model_not_supported(
        self,
        mock_groq,
        mock_get,
        mock_api_key,
        temp_cache_dir,
    ):
        """Test that a model failing the chat test is marked not_supported in get_models."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": [
                {"id": "llama-3.1-8b-instant", "object": "model"},
                {"id": "speech-model-v1", "object": "model"},
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # First Groq() call: chat test for llama (succeeds)
        # Second Groq() call: tool test for llama (succeeds)
        # Third Groq() call: chat test for speech-model (fails with "does not support chat completions")
        call_count = [0]

        def create_mock_client(*_args, **_kwargs):
            mock_client = MagicMock()
            if call_count[0] <= 1:
                # chat + tool test for llama: succeed
                mock_client.chat.completions.create.return_value = MagicMock()
            else:
                # chat test for speech-model: fails
                mock_client.chat.completions.create.side_effect = ValueError(
                    "Error: model 'speech-model-v1' does not support chat completions"
                )
            call_count[0] += 1
            return mock_client

        mock_groq.side_effect = create_mock_client

        discovery = GroqModelDiscovery(api_key=mock_api_key)
        discovery.CACHE_FILE = temp_cache_dir / ".cache" / "test_cache.json"

        models = discovery.get_models(force_refresh=True)

        # llama should be a normal LLM model with tool_calling
        assert "tool_calling" in models["llama-3.1-8b-instant"]
        assert models["llama-3.1-8b-instant"].get("not_supported") is None

        # speech-model should be marked not_supported
        assert models["speech-model-v1"]["not_supported"] is True
        assert "tool_calling" not in models["speech-model-v1"]

    @patch("lfx.base.models.groq_model_discovery.requests.get")
    @patch("groq.Groq")
    def test_transient_chat_error_does_not_exclude_model(
        self,
        mock_groq,
        mock_get,
        mock_api_key,
        temp_cache_dir,
    ):
        """Test that transient chat errors (rate limits) don't incorrectly exclude models."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": [
                {"id": "rate-limited-model", "object": "model"},
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # First Groq() call: chat test hits rate limit (transient error)
        # Second Groq() call: tool test succeeds
        call_count = [0]

        def create_mock_client(*_args, **_kwargs):
            mock_client = MagicMock()
            if call_count[0] == 0:
                mock_client.chat.completions.create.side_effect = RuntimeError("Rate limit exceeded")
            else:
                mock_client.chat.completions.create.return_value = MagicMock()
            call_count[0] += 1
            return mock_client

        mock_groq.side_effect = create_mock_client

        discovery = GroqModelDiscovery(api_key=mock_api_key)
        discovery.CACHE_FILE = temp_cache_dir / ".cache" / "test_cache.json"

        models = discovery.get_models(force_refresh=True)

        # Model should NOT be excluded — it should be treated as a normal LLM
        assert "tool_calling" in models["rate-limited-model"]
        assert models["rate-limited-model"].get("not_supported") is None
