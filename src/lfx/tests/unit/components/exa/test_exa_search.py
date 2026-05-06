"""Unit tests for the Exa Search component."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def component():
    """Build an ExaSearchToolkit with sensible defaults set."""
    from lfx.components.exa.exa_search import ExaSearchToolkit

    c = ExaSearchToolkit()
    c.exa_api_key = "test-key"
    c.metaphor_api_key = ""
    c.search_type = "auto"
    c.search_num_results = 10
    c.include_highlights = True
    c.highlights_max_characters = 0
    c.include_text = False
    c.category = ""
    c.max_age_hours = 0
    c.include_domains = ""
    c.exclude_domains = ""
    c.start_published_date = ""
    c.end_published_date = ""
    return c


def test_component_metadata():
    """Class name and component name must stay stable for saved flows."""
    from lfx.components.exa.exa_search import ExaSearchToolkit

    assert ExaSearchToolkit.__name__ == "ExaSearchToolkit"
    assert ExaSearchToolkit.name == "ExaSearch"


def test_resolved_api_key_prefers_exa_key(component):
    """`exa_api_key` wins when both are set."""
    component.metaphor_api_key = "legacy"
    assert component._resolved_api_key() == "test-key"


def test_resolved_api_key_falls_back_to_metaphor(component):
    """Old saved flows that only have `metaphor_api_key` keep working."""
    component.exa_api_key = ""
    component.metaphor_api_key = "legacy"
    assert component._resolved_api_key() == "legacy"


def test_build_client_sets_integration_header(component):
    """Client should be built with the API key and the integration header."""
    with patch("lfx.components.exa.exa_search.Exa") as mock_exa:
        mock_exa.return_value.headers = {}
        client = component._build_client()
        mock_exa.assert_called_once_with(api_key="test-key")
        assert client.headers["x-exa-integration"] == "langflow-integration"


def test_highlights_value_default_true(component):
    """Default highlights config is just `True`."""
    assert component._highlights_value() is True


def test_highlights_value_with_max_characters(component):
    """Setting max characters returns the dict shape Exa expects."""
    component.highlights_max_characters = 200
    assert component._highlights_value() == {"max_characters": 200}


def test_highlights_value_disabled(component):
    """Turning highlights off returns None so it's omitted from the payload."""
    component.include_highlights = False
    assert component._highlights_value() is None


def test_contents_default_payload(component):
    """Default contents payload only includes highlights."""
    assert component._contents() == {"highlights": True}


def test_contents_with_text_and_max_age(component):
    """Text and max_age_hours are included alongside highlights when set."""
    component.include_text = True
    component.max_age_hours = 24
    assert component._contents() == {
        "highlights": True,
        "text": True,
        "max_age_hours": 24,
    }


def test_contents_returns_none_when_everything_off(component):
    """No highlights, no text, no max_age -> no contents dict at all."""
    component.include_highlights = False
    component.include_text = False
    component.max_age_hours = 0
    assert component._contents() is None


def test_split_csv_handles_spaces_and_empty():
    """Domain lists are split, trimmed, and `None` when empty."""
    from lfx.components.exa.exa_search import ExaSearchToolkit

    assert ExaSearchToolkit._split_csv("a.com, b.com ,c.com") == [
        "a.com",
        "b.com",
        "c.com",
    ]
    assert ExaSearchToolkit._split_csv("") is None
    assert ExaSearchToolkit._split_csv("   ") is None


def test_build_toolkit_exposes_two_tools(component):
    """Toolkit must expose exactly `search` and `get_contents` (no find_similar)."""
    with patch("lfx.components.exa.exa_search.Exa") as mock_exa:
        mock_exa.return_value.headers = {}
        tools = component.build_toolkit()
        assert [t.name for t in tools] == ["search", "get_contents"]


def test_search_tool_default_kwargs(component):
    """Default search call uses type=auto, num_results=10, contents={highlights: True}."""
    mock_client = MagicMock()
    mock_client.headers = {}
    with patch("lfx.components.exa.exa_search.Exa", return_value=mock_client):
        tools = component.build_toolkit()
        search_tool = next(t for t in tools if t.name == "search")
        search_tool.invoke({"query": "hello"})
        mock_client.search.assert_called_once_with(
            "hello",
            type="auto",
            num_results=10,
            contents={"highlights": True},
        )


def test_search_tool_passes_filters(component):
    """Category, domain lists, and date filters should reach client.search()."""
    component.category = "company"
    component.include_domains = "a.com, b.com"
    component.exclude_domains = "spam.com"
    component.start_published_date = "2024-01-01"
    component.end_published_date = "2024-12-31"

    mock_client = MagicMock()
    mock_client.headers = {}
    with patch("lfx.components.exa.exa_search.Exa", return_value=mock_client):
        tools = component.build_toolkit()
        search_tool = next(t for t in tools if t.name == "search")
        search_tool.invoke({"query": "q"})

        call = mock_client.search.call_args
        assert call.kwargs["category"] == "company"
        assert call.kwargs["include_domains"] == ["a.com", "b.com"]
        assert call.kwargs["exclude_domains"] == ["spam.com"]
        assert call.kwargs["start_published_date"] == "2024-01-01"
        assert call.kwargs["end_published_date"] == "2024-12-31"


def test_get_contents_tool_kwargs(component):
    """get_contents passes highlights/text/max_age_hours as flat kwargs."""
    component.highlights_max_characters = 300
    component.include_text = True
    component.max_age_hours = 12

    mock_client = MagicMock()
    mock_client.headers = {}
    with patch("lfx.components.exa.exa_search.Exa", return_value=mock_client):
        tools = component.build_toolkit()
        get_contents_tool = next(t for t in tools if t.name == "get_contents")
        get_contents_tool.invoke({"ids": ["abc"]})

        mock_client.get_contents.assert_called_once_with(
            ["abc"],
            highlights={"max_characters": 300},
            text=True,
            max_age_hours=12,
        )
