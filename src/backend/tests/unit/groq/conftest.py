import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest
import requests


# Pytest configuration for custom markers and API key handling
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "requires_api_key: mark test as requiring a real GROQ_API_KEY from environment")


def pytest_collection_modifyitems(config, items):  # noqa: ARG001
    """Skip tests marked with requires_api_key if GROQ_API_KEY is not set."""
    skip_no_api_key = pytest.mark.skip(reason="GROQ_API_KEY not found in environment (.env)")

    for item in items:
        if "requires_api_key" in item.keywords and not os.getenv("GROQ_API_KEY"):
            item.add_marker(skip_no_api_key)


@pytest.fixture
def real_groq_api_key():
    """Get real GROQ_API_KEY from environment if available."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        pytest.skip("GROQ_API_KEY not found in environment")
    return api_key


@pytest.fixture
def mock_api_key():
    """Provide a mock API key for testing."""
    return "gsk_test_api_key_1234567890"


@pytest.fixture
def mock_invalid_api_key():
    """Provide an invalid API key for testing."""
    return "invalid_key"


@pytest.fixture
def mock_groq_models_response():
    """Mock response from Groq models API."""
    return {
        "data": [
            {"id": "llama-3.1-8b-instant", "object": "model"},
            {"id": "llama-3.3-70b-versatile", "object": "model"},
            {"id": "mixtral-8x7b-32768", "object": "model"},
            {"id": "gemma-7b-it", "object": "model"},
            {"id": "whisper-large-v3", "object": "model"},
            {"id": "distil-whisper-large-v3-en", "object": "model"},
            {"id": "meta-llama/llama-guard-4-12b", "object": "model"},
            {"id": "meta-llama/llama-prompt-guard-2-86m", "object": "model"},
        ]
    }


@pytest.fixture
def mock_llm_models():
    """List of LLM models (excluding audio, TTS, guards)."""
    return [
        "llama-3.1-8b-instant",
        "llama-3.3-70b-versatile",
        "mixtral-8x7b-32768",
        "gemma-7b-it",
    ]


@pytest.fixture
def mock_non_llm_models():
    """List of non-LLM models (audio, TTS, guards)."""
    return [
        "whisper-large-v3",
        "distil-whisper-large-v3-en",
        "meta-llama/llama-guard-4-12b",
        "meta-llama/llama-prompt-guard-2-86m",
    ]


@pytest.fixture
def mock_tool_calling_models():
    """List of models that support tool calling."""
    return ["llama-3.1-8b-instant", "llama-3.3-70b-versatile", "mixtral-8x7b-32768"]


@pytest.fixture
def mock_non_tool_calling_models():
    """List of models that don't support tool calling."""
    return ["gemma-7b-it"]


@pytest.fixture
def temp_cache_dir():
    """Create a temporary directory for cache files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_cache_file(temp_cache_dir):
    """Create a mock cache file with valid data."""
    cache_file = temp_cache_dir / ".cache" / "groq_models_cache.json"
    cache_file.parent.mkdir(parents=True, exist_ok=True)

    cache_data = {
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "models": {
            "llama-3.1-8b-instant": {
                "name": "llama-3.1-8b-instant",
                "provider": "Meta",
                "tool_calling": True,
                "preview": False,
                "last_tested": datetime.now(timezone.utc).isoformat(),
            },
            "llama-3.3-70b-versatile": {
                "name": "llama-3.3-70b-versatile",
                "provider": "Meta",
                "tool_calling": True,
                "preview": False,
                "last_tested": datetime.now(timezone.utc).isoformat(),
            },
        },
    }

    with cache_file.open("w") as f:
        json.dump(cache_data, f)

    return cache_file


@pytest.fixture
def mock_expired_cache_file(temp_cache_dir):
    """Create a mock cache file with expired data."""
    cache_file = temp_cache_dir / ".cache" / "groq_models_cache.json"
    cache_file.parent.mkdir(parents=True, exist_ok=True)

    # Set cache time to 25 hours ago (beyond 24 hour expiry)
    expired_time = datetime.now(timezone.utc) - timedelta(hours=25)

    cache_data = {
        "cached_at": expired_time.isoformat(),
        "models": {
            "llama-3.1-8b-instant": {
                "name": "llama-3.1-8b-instant",
                "provider": "Meta",
                "tool_calling": True,
                "preview": False,
                "last_tested": expired_time.isoformat(),
            }
        },
    }

    with cache_file.open("w") as f:
        json.dump(cache_data, f)

    return cache_file


@pytest.fixture
def mock_corrupted_cache_file(temp_cache_dir):
    """Create a corrupted cache file (invalid JSON)."""
    cache_file = temp_cache_dir / ".cache" / "groq_models_cache.json"
    cache_file.parent.mkdir(parents=True, exist_ok=True)

    with cache_file.open("w") as f:
        f.write("{ invalid json content }")

    return cache_file


@pytest.fixture
def mock_requests_get_success(mock_groq_models_response):
    """Mock successful requests.get for Groq API."""

    def _mock_get(_url, *_args, **_kwargs):
        response = Mock()
        response.status_code = 200
        response.json.return_value = mock_groq_models_response
        response.raise_for_status = Mock()
        return response

    return _mock_get


@pytest.fixture
def mock_requests_get_failure():
    """Mock failed requests.get for Groq API."""

    def _mock_get(_url, *_args, **_kwargs):
        msg = "Connection error"
        raise requests.RequestException(msg)

    return _mock_get


@pytest.fixture
def mock_requests_get_timeout():
    """Mock timeout for requests.get."""

    def _mock_get(_url, *_args, **_kwargs):
        msg = "Request timeout"
        raise requests.Timeout(msg)

    return _mock_get


@pytest.fixture
def mock_requests_get_unauthorized():
    """Mock unauthorized response (401) for requests.get."""

    def _mock_get(_url, *_args, **_kwargs):
        response = Mock()
        response.status_code = 401
        response.raise_for_status.side_effect = requests.HTTPError("401 Unauthorized")
        return response

    return _mock_get


@pytest.fixture
def mock_groq_client_tool_calling_success():
    """Mock successful Groq client for tool calling test."""

    def _create_mock_client(*_args, **_kwargs):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        return mock_client

    return _create_mock_client


@pytest.fixture
def mock_groq_client_tool_calling_failure():
    """Mock Groq client that raises error for tool calling."""

    def _create_mock_client(*_args, **_kwargs):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = ValueError("tool calling not supported for this model")
        return mock_client

    return _create_mock_client


@pytest.fixture
def mock_groq_client_rate_limit():
    """Mock Groq client that raises rate limit error."""

    def _create_mock_client(*_args, **_kwargs):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("Rate limit exceeded")
        return mock_client

    return _create_mock_client


@pytest.fixture
def sample_models_metadata():
    """Sample model metadata dictionary for testing."""
    return {
        "llama-3.1-8b-instant": {
            "name": "llama-3.1-8b-instant",
            "provider": "Meta",
            "tool_calling": True,
            "preview": False,
            "last_tested": datetime.now(timezone.utc).isoformat(),
        },
        "llama-3.3-70b-versatile": {
            "name": "llama-3.3-70b-versatile",
            "provider": "Meta",
            "tool_calling": True,
            "preview": False,
            "last_tested": datetime.now(timezone.utc).isoformat(),
        },
        "gemma-7b-it": {
            "name": "gemma-7b-it",
            "provider": "Google",
            "tool_calling": False,
            "preview": False,
            "last_tested": datetime.now(timezone.utc).isoformat(),
        },
        "llama-3.2-1b-preview": {
            "name": "llama-3.2-1b-preview",
            "provider": "Meta",
            "tool_calling": False,
            "preview": True,
            "last_tested": datetime.now(timezone.utc).isoformat(),
        },
        "whisper-large-v3": {
            "name": "whisper-large-v3",
            "provider": "OpenAI",
            "not_supported": True,
            "last_tested": datetime.now(timezone.utc).isoformat(),
        },
    }
