"""Shared JSON fixtures for unit testing.

This module provides reusable JSON data structures that appear frequently across unit tests.
Instead of recreating these JSON objects in every test file, import them from here.
"""

import json
from typing import Any
from uuid import uuid4

import pytest

# =============================================================================
# Standard API Response Structures (found in 25+ test files)
# =============================================================================

BASIC_FLOW_STRUCTURE = {
    "name": "Test Flow",
    "description": "A test flow for unit testing",
    "icon": "🔬",
    "icon_bg_color": "#ff00ff",
    "gradient": "linear-gradient(45deg, #ff0000, #00ff00)",
    "data": {},
    "is_component": False,
    "webhook": False,
    "endpoint_name": "test-endpoint",
    "tags": ["test", "unit-test"],
    "folder_id": str(uuid4()),
}

BASIC_API_SUCCESS_RESPONSE = {
    "status": "success",
    "message": "Operation completed successfully",
    "data": {"id": str(uuid4()), "timestamp": "2024-01-01T00:00:00Z", "result": "test result"},
}

BASIC_API_ERROR_RESPONSE = {
    "status": "error",
    "message": "Operation failed",
    "error": {"code": 400, "type": "ValidationError", "details": "Invalid input provided"},
    "timestamp": "2024-01-01T00:00:00Z",
}


@pytest.fixture
def basic_flow_json():
    """Standard flow JSON structure."""
    return BASIC_FLOW_STRUCTURE.copy()


@pytest.fixture
def api_success_response():
    """Standard API success response."""
    return BASIC_API_SUCCESS_RESPONSE.copy()


@pytest.fixture
def api_error_response():
    """Standard API error response."""
    return BASIC_API_ERROR_RESPONSE.copy()


# =============================================================================
# Component Configuration JSON (found in 30+ test files)
# =============================================================================

OPENAI_COMPONENT_CONFIG = {
    "model_name": "gpt-4o-mini",
    "api_key": "test-openai-key",
    "temperature": 0.7,
    "max_tokens": 1000,
    "top_p": 1.0,
    "frequency_penalty": 0.0,
    "presence_penalty": 0.0,
    "seed": 42,
    "max_retries": 3,
    "timeout": 600,
    "openai_api_base": "https://api.openai.com/v1",
}

ANTHROPIC_COMPONENT_CONFIG = {
    "model_name": "claude-3-sonnet-20240229",
    "api_key": "test-anthropic-key",
    "temperature": 0.7,
    "max_tokens": 1000,
    "top_p": 1.0,
    "top_k": 250,
    "timeout": 600,
    "anthropic_api_url": "https://api.anthropic.com",
}

RETRIEVER_COMPONENT_CONFIG = {
    "k": 3,
    "similarity_threshold": 0.7,
    "search_type": "similarity",
    "metadata_filter": {},
    "score_threshold": 0.0,
}

EMBEDDING_COMPONENT_CONFIG = {
    "model_name": "text-embedding-ada-002",
    "api_key": "test-embedding-key",
    "dimensions": 1536,
    "batch_size": 1000,
    "timeout": 30,
}


@pytest.fixture
def openai_config():
    """OpenAI component configuration."""
    return OPENAI_COMPONENT_CONFIG.copy()


@pytest.fixture
def anthropic_config():
    """Anthropic component configuration."""
    return ANTHROPIC_COMPONENT_CONFIG.copy()


@pytest.fixture
def retriever_config():
    """Retriever component configuration."""
    return RETRIEVER_COMPONENT_CONFIG.copy()


@pytest.fixture
def embedding_config():
    """Embedding component configuration."""
    return EMBEDDING_COMPONENT_CONFIG.copy()


# =============================================================================
# Sample Data Structures (found in 20+ test files)
# =============================================================================

SAMPLE_USER_DATA = {
    "users": [
        {
            "id": 1,
            "username": "testuser1",
            "email": "test1@example.com",
            "is_active": True,
            "created_at": "2024-01-01T00:00:00Z",
        },
        {
            "id": 2,
            "username": "testuser2",
            "email": "test2@example.com",
            "is_active": True,
            "created_at": "2024-01-02T00:00:00Z",
        },
    ],
    "total": 2,
    "page": 1,
    "per_page": 10,
}

SAMPLE_DOCUMENT_DATA = [
    {
        "id": 1,
        "title": "Test Document 1",
        "content": "This is the content of test document 1. It contains useful information for testing.",
        "metadata": {"source": "test", "category": "documentation", "tags": ["test", "sample"]},
        "score": 0.95,
    },
    {
        "id": 2,
        "title": "Test Document 2",
        "content": "This is the content of test document 2. It also contains test information.",
        "metadata": {"source": "test", "category": "guide", "tags": ["test", "example"]},
        "score": 0.87,
    },
    {
        "id": 3,
        "title": "Test Document 3",
        "content": "This is the content of test document 3. More test content here.",
        "metadata": {"source": "test", "category": "reference", "tags": ["test", "reference"]},
        "score": 0.82,
    },
]

SAMPLE_CONVERSATION_DATA = {
    "conversation_id": str(uuid4()),
    "messages": [
        {"id": str(uuid4()), "role": "user", "content": "Hello, how are you?", "timestamp": "2024-01-01T10:00:00Z"},
        {
            "id": str(uuid4()),
            "role": "assistant",
            "content": "I'm doing well, thank you! How can I help you today?",
            "timestamp": "2024-01-01T10:00:05Z",
        },
        {
            "id": str(uuid4()),
            "role": "user",
            "content": "I need help with testing my application.",
            "timestamp": "2024-01-01T10:01:00Z",
        },
    ],
    "metadata": {
        "user_id": str(uuid4()),
        "session_id": str(uuid4()),
        "created_at": "2024-01-01T10:00:00Z",
        "updated_at": "2024-01-01T10:01:00Z",
    },
}


@pytest.fixture
def sample_user_data():
    """Sample user data structure."""
    return json.loads(json.dumps(SAMPLE_USER_DATA))


@pytest.fixture
def sample_document_data():
    """Sample document data structure."""
    return json.loads(json.dumps(SAMPLE_DOCUMENT_DATA))


@pytest.fixture
def sample_conversation_data():
    """Sample conversation data structure."""
    return json.loads(json.dumps(SAMPLE_CONVERSATION_DATA))


# =============================================================================
# External API Response Structures
# =============================================================================

OPENAI_API_RESPONSE = {
    "id": "chatcmpl-test123",
    "object": "chat.completion",
    "created": 1677858242,
    "model": "gpt-4o-mini",
    "usage": {"prompt_tokens": 13, "completion_tokens": 7, "total_tokens": 20},
    "choices": [
        {
            "message": {"role": "assistant", "content": "This is a mock OpenAI response for testing purposes."},
            "finish_reason": "stop",
            "index": 0,
        }
    ],
}

ANTHROPIC_API_RESPONSE = {
    "id": "msg_test123",
    "type": "message",
    "role": "assistant",
    "content": [{"type": "text", "text": "This is a mock Anthropic response for testing purposes."}],
    "model": "claude-3-sonnet-20240229",
    "stop_reason": "end_turn",
    "stop_sequence": None,
    "usage": {"input_tokens": 13, "output_tokens": 12},
}

GOOGLE_SEARCH_RESPONSE = {
    "searchInformation": {"searchTime": 0.45, "totalResults": "1000000"},
    "items": [
        {
            "title": "Test Search Result 1",
            "link": "https://example.com/result1",
            "snippet": "This is a test search result snippet with relevant information.",
            "displayLink": "example.com",
        },
        {
            "title": "Test Search Result 2",
            "link": "https://example.com/result2",
            "snippet": "Another test search result snippet with more test information.",
            "displayLink": "example.com",
        },
    ],
}

EMBEDDING_API_RESPONSE = {
    "object": "list",
    "data": [
        {
            "object": "embedding",
            "embedding": [0.1] * 1536,  # Mock 1536-dimensional embedding
            "index": 0,
        },
        {
            "object": "embedding",
            "embedding": [0.2] * 1536,  # Another mock embedding
            "index": 1,
        },
    ],
    "model": "text-embedding-ada-002",
    "usage": {"prompt_tokens": 8, "total_tokens": 8},
}


@pytest.fixture
def openai_api_response():
    """OpenAI API response structure."""
    return json.loads(json.dumps(OPENAI_API_RESPONSE))


@pytest.fixture
def anthropic_api_response():
    """Anthropic API response structure."""
    return json.loads(json.dumps(ANTHROPIC_API_RESPONSE))


@pytest.fixture
def google_search_response():
    """Google Search API response structure."""
    return json.loads(json.dumps(GOOGLE_SEARCH_RESPONSE))


@pytest.fixture
def embedding_api_response():
    """Embedding API response structure."""
    return json.loads(json.dumps(EMBEDDING_API_RESPONSE))


# =============================================================================
# Database Record Structures
# =============================================================================

SAMPLE_DATABASE_RECORDS = [
    {
        "id": 1,
        "name": "Test Record 1",
        "value": "test_value_1",
        "category": "A",
        "active": True,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    },
    {
        "id": 2,
        "name": "Test Record 2",
        "value": "test_value_2",
        "category": "B",
        "active": True,
        "created_at": "2024-01-02T00:00:00Z",
        "updated_at": "2024-01-02T00:00:00Z",
    },
    {
        "id": 3,
        "name": "Test Record 3",
        "value": "test_value_3",
        "category": "A",
        "active": False,
        "created_at": "2024-01-03T00:00:00Z",
        "updated_at": "2024-01-03T00:00:00Z",
    },
]


@pytest.fixture
def sample_database_records():
    """Sample database records."""
    return json.loads(json.dumps(SAMPLE_DATABASE_RECORDS))


# =============================================================================
# Error Response Structures
# =============================================================================

VALIDATION_ERROR_RESPONSE = {
    "detail": [
        {"loc": ["body", "field_name"], "msg": "field required", "type": "value_error.missing"},
        {
            "loc": ["body", "another_field"],
            "msg": "ensure this value has at least 1 characters",
            "type": "value_error.any_str.min_length",
            "ctx": {"limit_value": 1},
        },
    ]
}

HTTP_ERROR_RESPONSES = {
    400: {"error": "Bad Request", "message": "The request was invalid or cannot be served", "code": 400},
    401: {"error": "Unauthorized", "message": "Authentication credentials were missing or incorrect", "code": 401},
    403: {"error": "Forbidden", "message": "The request was valid, but the server is refusing action", "code": 403},
    404: {"error": "Not Found", "message": "The requested resource could not be found", "code": 404},
    500: {"error": "Internal Server Error", "message": "An internal server error occurred", "code": 500},
}


@pytest.fixture
def validation_error_response():
    """Standard validation error response."""
    return json.loads(json.dumps(VALIDATION_ERROR_RESPONSE))


@pytest.fixture
def http_error_responses():
    """Standard HTTP error responses."""
    return json.loads(json.dumps(HTTP_ERROR_RESPONSES))


# =============================================================================
# Utility Functions for JSON Fixtures
# =============================================================================


def create_test_flow_json(
    name: str = "Test Flow", description: str = "Test description", **overrides
) -> dict[str, Any]:
    """Create a test flow JSON with custom values."""
    flow_data = BASIC_FLOW_STRUCTURE.copy()
    flow_data.update({"name": name, "description": description, **overrides})
    return flow_data


def create_test_api_response(status: str = "success", data: Any = None, **overrides) -> dict[str, Any]:
    """Create a test API response with custom values."""
    response_data = BASIC_API_SUCCESS_RESPONSE.copy()
    if data is not None:
        response_data["data"] = data
    response_data.update({"status": status, **overrides})
    return response_data


def create_mock_component_config(component_type: str = "llm", **overrides) -> dict[str, Any]:
    """Create a mock component config based on type."""
    configs = {
        "openai": OPENAI_COMPONENT_CONFIG,
        "anthropic": ANTHROPIC_COMPONENT_CONFIG,
        "retriever": RETRIEVER_COMPONENT_CONFIG,
        "embedding": EMBEDDING_COMPONENT_CONFIG,
    }

    base_config = configs.get(component_type, OPENAI_COMPONENT_CONFIG).copy()
    base_config.update(overrides)
    return base_config
