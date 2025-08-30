"""Mock data objects and factories for unit testing.

This module provides reusable Data, Message, and other Langflow objects
that are frequently created across different unit tests.
"""

from typing import Any
from uuid import uuid4

import pytest

# Conditional imports for testing environment
try:
    from langflow.schema import Data
    from langflow.schema.dotdict import dotdict
    from langflow.schema.message import Message
except ImportError:
    # Fallback for when langflow modules are not available
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

    dotdict = dict


# =============================================================================
# Data Object Factories (frequently recreated in tests)
# =============================================================================


def create_sample_data(
    count: int = 3,
    text_prefix: str = "Sample document",
    *,
    include_metadata: bool = True,
    metadata_template: dict[str, Any] | None = None,
) -> list[Data]:
    """Create sample Data objects for testing.

    Args:
        count: Number of Data objects to create
        text_prefix: Prefix for text content
        include_metadata: Whether to include metadata
        metadata_template: Template for metadata (uses defaults if None)

    Returns:
        List of Data objects
    """
    data_objects = []
    default_metadata = {"source": "test", "category": "sample", "score": 0.9}

    for i in range(count):
        text = f"{text_prefix} {i + 1}"

        if include_metadata:
            metadata = metadata_template.copy() if metadata_template else default_metadata.copy()
            metadata.update({"id": i + 1, "index": i})
        else:
            metadata = None

        data_objects.append(Data(text=text, data=metadata))

    return data_objects


def create_sample_messages(
    count: int = 3, sender_prefix: str = "user", content_prefix: str = "Test message", *, alternate_senders: bool = True
) -> list[Message]:
    """Create sample Message objects for testing.

    Args:
        count: Number of messages to create
        sender_prefix: Prefix for sender name
        content_prefix: Prefix for message content
        alternate_senders: Whether to alternate between user/assistant

    Returns:
        List of Message objects
    """
    messages = []
    senders = ["user", "assistant"] if alternate_senders else [sender_prefix]

    for i in range(count):
        sender = senders[i % len(senders)]
        content = f"{content_prefix} {i + 1}"

        messages.append(
            Message(
                text=content, sender=sender, sender_name=f"{sender}_{i + 1}" if alternate_senders else sender_prefix
            )
        )

    return messages


def create_conversation_data(message_count: int = 5, session_id: str | None = None) -> dict[str, Any]:
    """Create conversation data structure.

    Args:
        message_count: Number of messages in conversation
        session_id: Session ID (generates if None)

    Returns:
        Conversation data dictionary
    """
    if session_id is None:
        session_id = str(uuid4())

    messages = create_sample_messages(count=message_count, alternate_senders=True)

    return {
        "session_id": session_id,
        "messages": [
            {"id": str(uuid4()), "text": msg.text, "sender": msg.sender, "timestamp": f"2024-01-01T10:{i:02d}:00Z"}
            for i, msg in enumerate(messages)
        ],
        "metadata": {"created_at": "2024-01-01T10:00:00Z", "message_count": len(messages)},
    }


# =============================================================================
# Pre-built Data Sets (commonly used across tests)
# =============================================================================

STANDARD_TEST_DATA = create_sample_data(
    count=3,
    text_prefix="Standard test document",
    metadata_template={"source": "test_suite", "type": "standard", "category": "testing"},
)

LARGE_TEST_DATA = create_sample_data(
    count=100,
    text_prefix="Large dataset document",
    metadata_template={"source": "performance_test", "type": "bulk", "category": "performance"},
)

CONVERSATION_MESSAGES = create_sample_messages(count=6, content_prefix="Conversation message", alternate_senders=True)

SEARCH_RESULT_DATA = [
    Data(
        text="Machine learning is a subset of artificial intelligence.",
        data={
            "title": "Introduction to Machine Learning",
            "url": "https://example.com/ml-intro",
            "score": 0.95,
            "source": "search",
        },
    ),
    Data(
        text="Deep learning uses neural networks with multiple layers.",
        data={
            "title": "Deep Learning Fundamentals",
            "url": "https://example.com/dl-fundamentals",
            "score": 0.89,
            "source": "search",
        },
    ),
    Data(
        text="Natural language processing enables computers to understand text.",
        data={"title": "NLP Overview", "url": "https://example.com/nlp-overview", "score": 0.82, "source": "search"},
    ),
]

EMBEDDING_TEST_DATA = [
    Data(
        text="This is a test sentence for embedding.",
        data={"embedding": [0.1] * 768, "model": "text-embedding-ada-002", "dimensions": 768},
    ),
    Data(
        text="Another test sentence with different content.",
        data={"embedding": [0.2] * 768, "model": "text-embedding-ada-002", "dimensions": 768},
    ),
]


@pytest.fixture
def standard_test_data():
    """Standard test data objects."""
    return [data.copy() for data in STANDARD_TEST_DATA]


@pytest.fixture
def large_test_data():
    """Large test dataset for performance testing."""
    return [data.copy() for data in LARGE_TEST_DATA]


@pytest.fixture
def conversation_messages():
    """Standard conversation messages."""
    return [Message(text=msg.text, sender=msg.sender) for msg in CONVERSATION_MESSAGES]


@pytest.fixture
def search_result_data():
    """Sample search result data."""
    return [data.copy() for data in SEARCH_RESULT_DATA]


@pytest.fixture
def embedding_test_data():
    """Sample embedding data."""
    return [data.copy() for data in EMBEDDING_TEST_DATA]


# =============================================================================
# Specialized Data Factories
# =============================================================================


def create_retrieval_data(
    query: str = "test query", k: int = 3, similarity_scores: list[float] | None = None
) -> list[Data]:
    """Create mock retrieval results.

    Args:
        query: The query string
        k: Number of results to return
        similarity_scores: Custom similarity scores

    Returns:
        List of Data objects representing retrieval results
    """
    if similarity_scores is None:
        similarity_scores = [0.9 - (i * 0.1) for i in range(k)]

    results = []
    for i in range(k):
        score = similarity_scores[i] if i < len(similarity_scores) else 0.5

        results.append(
            Data(
                text=f"Retrieved document {i + 1} for query: {query}",
                data={"id": i + 1, "query": query, "score": score, "rank": i + 1, "source": "retrieval_test"},
            )
        )

    return results


def create_processing_data(
    input_texts: list[str], operation: str = "transform", *, include_original: bool = True
) -> list[Data]:
    """Create data for processing component tests.

    Args:
        input_texts: List of input text strings
        operation: Processing operation name
        include_original: Whether to include original text in metadata

    Returns:
        List of processed Data objects
    """
    processed_data = []

    for i, text in enumerate(input_texts):
        # Apply mock processing based on operation
        if operation == "uppercase":
            processed_text = text.upper()
        elif operation == "lowercase":
            processed_text = text.lower()
        elif operation == "reverse":
            processed_text = text[::-1]
        else:
            processed_text = f"processed_{text}"

        data = Data(text=processed_text)

        if include_original:
            data.data = {"original": text, "operation": operation, "index": i, "processed_at": "2024-01-01T00:00:00Z"}

        processed_data.append(data)

    return processed_data


def create_agent_tool_data(
    tool_name: str = "test_tool", action: str = "search", result: Any = "tool result", *, success: bool = True
) -> Data:
    """Create mock agent tool execution data.

    Args:
        tool_name: Name of the tool
        action: Action performed
        result: Tool execution result
        success: Whether execution was successful

    Returns:
        Data object representing tool execution
    """
    return Data(
        text=f"Tool '{tool_name}' executed action '{action}'"
        + (f" successfully: {result}" if success else f" failed: {result}"),
        data={
            "tool_name": tool_name,
            "action": action,
            "result": result,
            "success": success,
            "execution_time": 0.1,
            "timestamp": "2024-01-01T00:00:00Z",
        },
    )


# =============================================================================
# Pytest Fixtures for Data Factories
# =============================================================================


@pytest.fixture
def data_factory():
    """Factory for creating Data objects."""
    return create_sample_data


@pytest.fixture
def message_factory():
    """Factory for creating Message objects."""
    return create_sample_messages


@pytest.fixture
def retrieval_factory():
    """Factory for creating retrieval data."""
    return create_retrieval_data


@pytest.fixture
def processing_factory():
    """Factory for creating processing data."""
    return create_processing_data


# =============================================================================
# Edge Case Data Sets
# =============================================================================

EDGE_CASE_DATA = [
    # Empty data
    Data(text="", data={}),
    # Very long text
    Data(
        text="A" * 10000,  # 10k character string
        data={"length": 10000, "type": "long_text"},
    ),
    # Special characters
    Data(text="Special chars: !@#$%^&*()[]{}|;:,.<>?", data={"type": "special_chars"}),
    # Unicode text
    Data(text="Unicode: 你好世界 🌍 café naïve résumé", data={"type": "unicode", "languages": ["zh", "emoji", "fr"]}),
    # Numeric text
    Data(text="123456789", data={"type": "numeric", "value": 123456789}),
    # JSON-like text
    Data(text='{"key": "value", "nested": {"array": [1, 2, 3]}}', data={"type": "json_like"}),
]


@pytest.fixture
def edge_case_data():
    """Edge case data for testing robustness."""
    return [data.copy() for data in EDGE_CASE_DATA]


# =============================================================================
# Data Validation Helpers
# =============================================================================


def validate_data_structure(data_obj: Data, required_fields: list[str] | None = None) -> bool:
    """Validate Data object structure.

    Args:
        data_obj: Data object to validate
        required_fields: List of required metadata fields

    Returns:
        True if valid, False otherwise
    """
    if not isinstance(data_obj, Data):
        return False

    # Check basic structure
    if not hasattr(data_obj, "text") and not hasattr(data_obj, "data"):
        return False

    # Check required fields in metadata
    if required_fields and data_obj.data:
        for field in required_fields:
            if field not in data_obj.data:
                return False

    return True


def validate_message_structure(message: Message) -> bool:
    """Validate Message object structure.

    Args:
        message: Message object to validate

    Returns:
        True if valid, False otherwise
    """
    if not isinstance(message, Message):
        return False

    required_attrs = ["text", "sender"]
    return all(hasattr(message, attr) for attr in required_attrs)


# =============================================================================
# Utility Functions
# =============================================================================


def merge_data_objects(data_list: list[Data], separator: str = "\n") -> Data:
    """Merge multiple Data objects into one.

    Args:
        data_list: List of Data objects to merge
        separator: Separator for joining text content

    Returns:
        Single merged Data object
    """
    if not data_list:
        return Data(text="", data={})

    merged_text = separator.join([d.text or "" for d in data_list])
    merged_data = {}

    # Merge metadata from all objects
    for i, data_obj in enumerate(data_list):
        if data_obj.data:
            merged_data[f"source_{i}"] = data_obj.data

    merged_data["merged_count"] = len(data_list)
    merged_data["merged_at"] = "2024-01-01T00:00:00Z"

    return Data(text=merged_text, data=merged_data)
