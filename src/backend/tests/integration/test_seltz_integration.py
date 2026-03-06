import os

import pytest

SELTZ_API_KEY = os.environ.get("SELTZ_API_KEY", "")


@pytest.fixture
def _seltz_available():
    """Skip tests if seltz package is not available or no API key is set."""
    if not SELTZ_API_KEY:
        pytest.skip("SELTZ_API_KEY environment variable not set")
    try:
        from seltz import Seltz

        Seltz(api_key=SELTZ_API_KEY)
    except Exception:
        pytest.skip("seltz package not available or has dependency conflicts in this environment")


@pytest.mark.usefixtures("_seltz_available")
@pytest.mark.api_key_required
@pytest.mark.no_blockbuster
class TestSeltzIntegration:
    """Integration tests for the Seltz Search component.

    These tests make real API calls to the Seltz API.
    Requires the SELTZ_API_KEY environment variable to be set.
    Skipped automatically if the seltz package cannot be loaded
    (e.g. due to protobuf version conflicts with other project dependencies).
    """

    def test_search_returns_results(self):
        from lfx.components.seltz.seltz_search import SeltzSearchToolkit

        component = SeltzSearchToolkit(api_key=SELTZ_API_KEY, max_documents=5)
        tools = component.build_toolkit()
        assert len(tools) == 1

        result = tools[0].invoke({"query": "what is langflow"})

        assert isinstance(result, list)
        assert len(result) > 0
        for doc in result:
            assert "url" in doc
            assert "content" in doc
            assert isinstance(doc["url"], str)
            assert isinstance(doc["content"], str)

    def test_search_respects_max_documents(self):
        from lfx.components.seltz.seltz_search import SeltzSearchToolkit

        component = SeltzSearchToolkit(api_key=SELTZ_API_KEY, max_documents=3)
        tools = component.build_toolkit()
        result = tools[0].invoke({"query": "python programming"})

        assert isinstance(result, list)
        assert len(result) <= 3

    def test_search_with_context(self):
        from lfx.components.seltz.seltz_search import SeltzSearchToolkit

        component = SeltzSearchToolkit(
            api_key=SELTZ_API_KEY,
            max_documents=5,
            context="user is looking for official documentation",
        )
        tools = component.build_toolkit()
        result = tools[0].invoke({"query": "python asyncio"})

        assert isinstance(result, list)
        assert len(result) > 0
        for doc in result:
            assert "url" in doc
            assert "content" in doc

    def test_search_different_queries(self):
        from lfx.components.seltz.seltz_search import SeltzSearchToolkit

        component = SeltzSearchToolkit(api_key=SELTZ_API_KEY, max_documents=5)
        tools = component.build_toolkit()

        result1 = tools[0].invoke({"query": "artificial intelligence"})
        result2 = tools[0].invoke({"query": "quantum computing"})

        assert isinstance(result1, list)
        assert isinstance(result2, list)
        assert len(result1) > 0
        assert len(result2) > 0
