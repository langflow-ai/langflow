"""Shared mock objects for unit testing.

This module provides reusable mock objects that appear frequently across unit tests.
Instead of recreating these mocks in every test file, import them from here.
"""

import json
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

# Conditional imports for testing environment
try:
    from langflow.custom import Component
    from langflow.graph.graph.base import Graph
    from langflow.graph.vertex.base import Vertex
    from langflow.schema import Data
    from langflow.schema.message import Message
except ImportError:
    # Fallback for when langflow modules are not available
    class Component:
        pass

    class Graph:
        pass

    class Vertex:
        pass

    class Data:
        def __init__(self, text="", data=None):
            self.text = text
            self.data = data or {}

        def copy(self):
            return Data(text=self.text, data=self.data.copy())

    class Message:
        def __init__(self, text="", sender="", sender_name=""):
            self.text = text
            self.sender = sender
            self.sender_name = sender_name


# =============================================================================
# Mock Language Models (found in 20+ test files)
# =============================================================================


class StandardMockLLM:
    """Standard mock language model used across tests."""

    def __init__(self, response_template: str = "Mock response: {input}"):
        self.response_template = response_template
        self.call_count = 0
        self.last_input = None

    def __call__(self, input_text: str) -> str:
        self.call_count += 1
        self.last_input = input_text
        return self.response_template.format(input=input_text)

    async def agenerate(self, messages: list[dict], **_kwargs) -> Mock:
        """Async generate method for LangChain compatibility."""
        content = messages[-1].get("content", "") if messages else ""
        mock_response = Mock()
        mock_response.generations = [[Mock()]]
        mock_response.generations[0][0].text = self.response_template.format(input=content)
        return mock_response

    def reset(self):
        """Reset call tracking."""
        self.call_count = 0
        self.last_input = None


@pytest.fixture
def mock_llm():
    """Standard mock LLM fixture."""
    return StandardMockLLM()


@pytest.fixture
def mock_openai_response():
    """Standard OpenAI API response structure."""
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message = Mock()
    mock_response.choices[0].message.content = "Mock OpenAI response"
    mock_response.usage = Mock()
    mock_response.usage.total_tokens = 100
    return mock_response


# =============================================================================
# Component Setup Mocks (found in 40+ test files)
# =============================================================================


@pytest.fixture
def standard_mock_vertex():
    """Standard mock vertex setup used across component tests."""
    mock_vertex = Mock(spec=Vertex)
    mock_vertex.graph = Mock(spec=Graph)
    mock_vertex.graph.session_id = str(uuid4())
    mock_vertex.graph.flow_id = str(uuid4())
    mock_vertex.id = str(uuid4())
    return mock_vertex


def create_mock_component_instance(component_class, vertex=None, **kwargs):
    """Create a standard mock component instance.

    This pattern appears in 40+ test files.
    """
    if vertex is None:
        vertex = Mock(spec=Vertex)
        vertex.graph = Mock(spec=Graph)
        vertex.graph.session_id = str(uuid4())
        vertex.graph.flow_id = str(uuid4())

    instance = component_class(**kwargs)
    instance._vertex = vertex
    instance._should_process_output = Mock(return_value=False)
    return instance


# =============================================================================
# Standard Default Kwargs (found in 30+ test files)
# =============================================================================

COMMON_COMPONENT_KWARGS = {
    "max_tokens": 1000,
    "temperature": 0.1,
    "timeout": 30,
    "api_key": "test-api-key",
}

OPENAI_COMPONENT_KWARGS = {
    **COMMON_COMPONENT_KWARGS,
    "model_name": "gpt-4o-mini",
    "openai_api_base": "https://api.openai.com/v1",
    "seed": 1,
    "max_retries": 3,
}

ANTHROPIC_COMPONENT_KWARGS = {
    **COMMON_COMPONENT_KWARGS,
    "model_name": "claude-3-sonnet-20240229",
    "anthropic_api_url": "https://api.anthropic.com",
}


@pytest.fixture
def openai_default_kwargs():
    """Standard OpenAI component kwargs."""
    return OPENAI_COMPONENT_KWARGS.copy()


@pytest.fixture
def anthropic_default_kwargs():
    """Standard Anthropic component kwargs."""
    return ANTHROPIC_COMPONENT_KWARGS.copy()


# =============================================================================
# HTTP Client Mocks (found in 15+ test files)
# =============================================================================


class MockHTTPResponse:
    """Standard mock HTTP response."""

    def __init__(self, status_code: int = 200, json_data: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._json_data = json_data or {"status": "success", "data": "mock response"}
        self.text = text or json.dumps(self._json_data)
        self.headers = {"content-type": "application/json"}

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            error_msg = f"HTTP {self.status_code} Error"
            raise ValueError(error_msg)


@pytest.fixture
def mock_http_success_response():
    """Standard successful HTTP response."""
    return MockHTTPResponse()


@pytest.fixture
def mock_http_error_response():
    """Standard error HTTP response."""
    return MockHTTPResponse(status_code=500, json_data={"error": "Internal Server Error", "code": 500})


@pytest.fixture
def mock_async_http_client():
    """Mock async HTTP client with common methods."""
    client = AsyncMock()

    # Standard success response
    success_response = MockHTTPResponse()
    client.get.return_value = success_response
    client.post.return_value = success_response
    client.put.return_value = success_response
    client.delete.return_value = success_response

    return client


# =============================================================================
# Database Mocks (found in 10+ test files)
# =============================================================================


@pytest.fixture
def mock_database_session():
    """Standard mock database session."""
    session = AsyncMock()

    # Common database operations
    session.add = Mock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    session.exec = AsyncMock()
    session.close = AsyncMock()

    # Standard query results
    mock_result = Mock()
    mock_result.first.return_value = Mock(id=1, name="Test Record")
    mock_result.all.return_value = [
        Mock(id=1, name="Record 1"),
        Mock(id=2, name="Record 2"),
    ]
    session.exec.return_value = mock_result

    return session


# =============================================================================
# Standard Data Objects (found in 25+ test files)
# =============================================================================

SAMPLE_DATA_OBJECTS = [
    Data(text="First document", data={"id": 1, "type": "text"}),
    Data(text="Second document", data={"id": 2, "type": "text"}),
    Data(text="Third document", data={"id": 3, "type": "text"}),
]

SAMPLE_MESSAGES = [
    Message(text="Hello, how are you?", sender="user"),
    Message(text="I'm doing well, thank you!", sender="assistant"),
    Message(text="What can you help me with?", sender="user"),
]


@pytest.fixture
def sample_data_objects():
    """Standard sample data objects."""
    return SAMPLE_DATA_OBJECTS.copy()


@pytest.fixture
def sample_messages():
    """Standard sample messages."""
    return SAMPLE_MESSAGES.copy()


# =============================================================================
# External Service Mocks
# =============================================================================


@pytest.fixture
def mock_google_search_results():
    """Standard Google search API results."""
    return [
        {"title": "Test Result 1", "link": "https://example.com/1", "snippet": "This is a test search result"},
        {"title": "Test Result 2", "link": "https://example.com/2", "snippet": "Another test search result"},
    ]


@pytest.fixture
def mock_embeddings_response():
    """Standard embeddings API response."""
    return {
        "data": [
            {"embedding": [0.1] * 768, "index": 0},
            {"embedding": [0.2] * 768, "index": 1},
        ],
        "usage": {"total_tokens": 10},
    }


# =============================================================================
# Error Mocks (common error patterns)
# =============================================================================


class MockAPIError(Exception):
    """Standard API error for testing."""

    def __init__(self, message: str = "API Error", status_code: int = 500):
        super().__init__(message)
        self.status_code = status_code
        self.response = Mock()
        self.response.status_code = status_code
        self.response.json.return_value = {"error": message}


@pytest.fixture
def mock_api_error():
    """Standard API error fixture."""
    return MockAPIError()


@pytest.fixture
def mock_timeout_error():
    """Standard timeout error fixture."""
    import asyncio

    return asyncio.TimeoutError("Request timeout")


# =============================================================================
# Validation Helpers (common assertion patterns)
# =============================================================================


def assert_standard_api_response(response, expected_status: int = 200):
    """Standard API response validation."""
    assert hasattr(response, "status_code")
    assert response.status_code == expected_status
    if expected_status == 200:
        assert hasattr(response, "json") or hasattr(response, "_json_data")


def assert_component_output(result, expected_type=None, min_count=None):
    """Standard component output validation."""
    assert result is not None
    if expected_type:
        assert isinstance(result, expected_type)
    if min_count and hasattr(result, "__len__"):
        assert len(result) >= min_count


def assert_data_object_valid(data_obj):
    """Standard Data object validation."""
    assert isinstance(data_obj, Data)
    assert hasattr(data_obj, "text") or hasattr(data_obj, "data")


def assert_message_valid(message):
    """Standard Message object validation."""
    assert isinstance(message, Message)
    assert hasattr(message, "text")
    assert hasattr(message, "sender")
