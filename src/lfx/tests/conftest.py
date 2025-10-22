from pathlib import Path
from unittest.mock import patch

import pytest


# Set up test data paths
def pytest_configure(config):  # noqa: ARG001
    """Configure pytest with data paths and check prerequisites."""
    # Check if langflow is installed first - fail fast
    try:
        import langflow  # noqa: F401

        pytest.exit(
            "\n"
            "=" * 80 + "\n"
            "ERROR: langflow is installed. These tests require langflow to NOT be installed.\n"
            "\n"
            "To fix this, run these commands:\n"
            "\n"
            "    cd src/lfx\n"
            "    uv sync\n"
            "    uv run pytest ...\n"
            "\n"
            "The lfx tests are designed to run in isolation from langflow to ensure proper\n"
            "packaging and dependency management.\n"
            "=" * 80 + "\n",
            returncode=1,
        )
    except ImportError:
        # Good, langflow is not installed
        pass

    # Set up test data paths
    data_path = Path(__file__).parent / "data"
    pytest.BASIC_EXAMPLE_PATH = data_path / "basic_example.json"
    pytest.COMPLEX_EXAMPLE_PATH = data_path / "complex_example.json"
    pytest.OPENAPI_EXAMPLE_PATH = data_path / "Openapi.json"
    pytest.GROUPED_CHAT_EXAMPLE_PATH = data_path / "grouped_chat.json"
    pytest.ONE_GROUPED_CHAT_EXAMPLE_PATH = data_path / "one_group_chat.json"
    pytest.VECTOR_STORE_GROUPED_EXAMPLE_PATH = data_path / "vector_store_grouped.json"
    pytest.WEBHOOK_TEST = data_path / "WebhookTest.json"
    pytest.BASIC_CHAT_WITH_PROMPT_AND_HISTORY = data_path / "BasicChatwithPromptandHistory.json"
    pytest.CHAT_INPUT = data_path / "ChatInputTest.json"
    pytest.TWO_OUTPUTS = data_path / "TwoOutputsTest.json"
    pytest.VECTOR_STORE_PATH = data_path / "Vector_store.json"
    pytest.SIMPLE_API_TEST = data_path / "SimpleAPITest.json"
    pytest.MEMORY_CHATBOT_NO_LLM = data_path / "MemoryChatbotNoLLM.json"
    pytest.ENV_VARIABLE_TEST = data_path / "env_variable_test.json"
    pytest.LOOP_TEST = data_path / "LoopTest.json"


def pytest_collection_modifyitems(config, items):  # noqa: ARG001
    """Automatically add markers based on test file location."""
    for item in items:
        if "tests/unit/" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "tests/integration/" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "tests/slow/" in str(item.fspath):
            item.add_marker(pytest.mark.slow)


@pytest.fixture
def use_noop_session():
    """Force the use of NoopSession for testing."""
    from lfx.services.session import NoopSession

    # Mock session_scope to always return NoopSession
    with patch("lfx.services.deps.session_scope") as mock_session_scope:
        mock_session_scope.return_value.__aenter__.return_value = NoopSession()
        mock_session_scope.return_value.__aexit__.return_value = None
        yield


# Additional fixtures for more comprehensive testing support
@pytest.fixture(name="session")
def session_fixture():
    """Create a mock session for testing."""
    from unittest.mock import MagicMock

    return MagicMock()


@pytest.fixture
def json_flow():
    """Basic example flow data as JSON string."""
    return pytest.BASIC_EXAMPLE_PATH.read_text(encoding="utf-8")


@pytest.fixture
def basic_graph_data():
    """Basic example flow data as dictionary."""
    import json

    with pytest.BASIC_EXAMPLE_PATH.open(encoding="utf-8") as f:
        return json.load(f)


# Test data fixtures for various flow types
@pytest.fixture
def json_flow_with_prompt_and_history():
    return pytest.BASIC_CHAT_WITH_PROMPT_AND_HISTORY.read_text(encoding="utf-8")


@pytest.fixture
def json_memory_chatbot_no_llm():
    return pytest.MEMORY_CHATBOT_NO_LLM.read_text(encoding="utf-8")


@pytest.fixture
def json_vector_store():
    return pytest.VECTOR_STORE_PATH.read_text(encoding="utf-8")


@pytest.fixture
def json_webhook_test():
    return pytest.WEBHOOK_TEST.read_text(encoding="utf-8")


@pytest.fixture
def json_chat_input():
    return pytest.CHAT_INPUT.read_text(encoding="utf-8")


@pytest.fixture
def json_two_outputs():
    return pytest.TWO_OUTPUTS.read_text(encoding="utf-8")


@pytest.fixture
def grouped_chat_json_flow():
    return pytest.GROUPED_CHAT_EXAMPLE_PATH.read_text(encoding="utf-8")


@pytest.fixture
def one_grouped_chat_json_flow():
    return pytest.ONE_GROUPED_CHAT_EXAMPLE_PATH.read_text(encoding="utf-8")


@pytest.fixture
def vector_store_grouped_json_flow():
    return pytest.VECTOR_STORE_GROUPED_EXAMPLE_PATH.read_text(encoding="utf-8")


@pytest.fixture
def json_simple_api_test():
    return pytest.SIMPLE_API_TEST.read_text(encoding="utf-8")


@pytest.fixture
def json_loop_test():
    return pytest.LOOP_TEST.read_text(encoding="utf-8")


# Simple client fixture for basic HTTP testing (without full langflow app dependencies)
@pytest.fixture(name="client")
async def simple_client_fixture():
    """Simple HTTP client for basic testing."""
    # For lfx-specific tests, we might not need the full langflow app
    # This is a placeholder that can be expanded as needed
    from httpx import AsyncClient

    async with AsyncClient(base_url="http://testserver") as client:
        yield client
