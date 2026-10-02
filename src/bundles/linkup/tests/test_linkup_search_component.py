"""Unit tests for the Linkup Search component (``lfx-linkup``).

``linkup-sdk`` is a hard runtime dep of the bundle, so the client class is
patched at the component module and returns real SDK response models.  No
network access is required.
"""

from __future__ import annotations

import asyncio
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from lfx_linkup import LinkupSearchComponent
from linkup import (
    LinkupSearchImageResult,
    LinkupSearchResults,
    LinkupSearchTextResult,
    LinkupSource,
    LinkupSourcedAnswer,
)

CLIENT_PATCH_TARGET = "lfx_linkup.components.linkup.linkup_search.LinkupClient"

SEARCH_RESULTS = LinkupSearchResults(
    results=[
        LinkupSearchTextResult(
            type="text",
            name="Result one",
            url="https://example.com/one",
            content="First content.",
            favicon="https://example.com/favicon.ico",
        ),
        LinkupSearchImageResult(type="image", name="An image", url="https://example.com/image.png"),
        LinkupSearchTextResult(
            type="text",
            name="Result two",
            url="https://example.com/two",
            content="Second content.",
            favicon="https://example.com/favicon.ico",
        ),
    ]
)

SOURCED_ANSWER = LinkupSourcedAnswer(
    answer="Langflow is a visual workflow builder.",
    sources=[
        LinkupSource(name="Langflow", url="https://www.langflow.org", snippet="Build AI agents.", favicon=""),
        LinkupSource(name="GitHub", url="https://github.com/langflow-ai/langflow", snippet="Repository.", favicon=""),
    ],
)


def _mock_client(response: object) -> MagicMock:
    client = MagicMock()
    client.search.return_value = response
    return client


@pytest.fixture
def component() -> LinkupSearchComponent:
    """Build a LinkupSearchComponent with sensible defaults set."""
    c = LinkupSearchComponent()
    c.query = "what is langflow"
    c.linkup_api_key = "test-key"  # pragma: allowlist secret
    c.depth = "standard"
    c.max_results = 10
    c.include_domains = ""
    c.exclude_domains = ""
    c.from_date = ""
    c.to_date = ""
    return c


def test_component_metadata():
    """Class name must stay stable for saved flows."""
    assert LinkupSearchComponent.__name__ == "LinkupSearchComponent"
    assert LinkupSearchComponent.icon == "Linkup"


def test_missing_api_key_raises(component):
    """No key set -> clear ValueError instead of an anonymous request."""
    component.linkup_api_key = ""
    with patch(CLIENT_PATCH_TARGET) as mock_client_cls, pytest.raises(ValueError, match="Linkup API key is required"):
        component.linkup_search()
    mock_client_cls.assert_not_called()


def test_missing_query_raises(component):
    """An empty query is rejected before calling the API."""
    component.query = "   "
    with patch(CLIENT_PATCH_TARGET) as mock_client_cls, pytest.raises(ValueError, match="Search query is required"):
        component.linkup_search()
    mock_client_cls.assert_not_called()


def test_client_built_with_api_key(component):
    """The client is built from the component's API key input."""
    with patch(CLIENT_PATCH_TARGET, return_value=_mock_client(SEARCH_RESULTS)) as mock_client_cls:
        component.linkup_search()
    mock_client_cls.assert_called_once_with(api_key="test-key")  # pragma: allowlist secret


def test_search_default_kwargs(component):
    """Defaults send depth, max_results and a timeout, and omit unset filters."""
    client = _mock_client(SEARCH_RESULTS)
    with patch(CLIENT_PATCH_TARGET, return_value=client):
        component.linkup_search()
    client.search.assert_called_once_with(
        "what is langflow",
        output_type="searchResults",
        depth="standard",
        timeout=120.0,
        max_results=10,
    )


def test_search_passes_filters(component):
    """Depth, domain lists and the date range reach client.search()."""
    component.depth = "deep"
    component.include_domains = "a.com, b.com"
    component.exclude_domains = "spam.com"
    component.from_date = "2025-01-01"
    component.to_date = "2025-12-31"
    client = _mock_client(SEARCH_RESULTS)
    with patch(CLIENT_PATCH_TARGET, return_value=client):
        component.linkup_search()
    kwargs = client.search.call_args.kwargs
    assert kwargs["depth"] == "deep"
    assert kwargs["include_domains"] == ["a.com", "b.com"]
    assert kwargs["exclude_domains"] == ["spam.com"]
    assert kwargs["from_date"] == date(2025, 1, 1)
    assert kwargs["to_date"] == date(2025, 12, 31)


def test_zero_max_results_uses_linkup_default(component):
    """max_results=0 leaves the result cap to Linkup."""
    component.max_results = 0
    client = _mock_client(SEARCH_RESULTS)
    with patch(CLIENT_PATCH_TARGET, return_value=client):
        component.linkup_search()
    assert "max_results" not in client.search.call_args.kwargs


def test_invalid_date_raises(component):
    """A malformed date is reported instead of being silently dropped."""
    component.from_date = "01/02/2025"
    client = _mock_client(SEARCH_RESULTS)
    with (
        patch(CLIENT_PATCH_TARGET, return_value=client),
        pytest.raises(ValueError, match="From Date must be an ISO date"),
    ):
        component.linkup_search()
    client.search.assert_not_called()


def test_split_csv_handles_spaces_and_empty():
    """Domain lists are split, trimmed, and `None` when empty."""
    assert LinkupSearchComponent._split_csv("a.com, b.com ,c.com") == ["a.com", "b.com", "c.com"]
    assert LinkupSearchComponent._split_csv("") is None
    assert LinkupSearchComponent._split_csv("  ,  ") is None


def test_linkup_search_maps_text_results(component):
    """Text results map to rows with title, url and content; image results are skipped."""
    with patch(CLIENT_PATCH_TARGET, return_value=_mock_client(SEARCH_RESULTS)):
        frame = component.linkup_search()
    assert len(frame) == 2
    assert list(frame["title"]) == ["Result one", "Result two"]
    assert list(frame["url"]) == ["https://example.com/one", "https://example.com/two"]
    assert list(frame["content"]) == ["First content.", "Second content."]


def test_linkup_search_handles_empty_results(component):
    """No results yields an empty table, not an error."""
    with patch(CLIENT_PATCH_TARGET, return_value=_mock_client(LinkupSearchResults(results=[]))):
        frame = component.linkup_search()
    assert len(frame) == 0


def test_linkup_sourced_answer(component):
    """The sourced answer output requests sourcedAnswer and lists the sources after the answer."""
    client = _mock_client(SOURCED_ANSWER)
    with patch(CLIENT_PATCH_TARGET, return_value=client):
        message = component.linkup_sourced_answer()
    assert client.search.call_args.kwargs["output_type"] == "sourcedAnswer"
    assert message.text == (
        "Langflow is a visual workflow builder.\n\n"
        "Sources:\n"
        "- [Langflow](https://www.langflow.org)\n"
        "- [GitHub](https://github.com/langflow-ai/langflow)"
    )


def test_linkup_sourced_answer_without_sources(component):
    """An answer without sources is returned as-is."""
    with patch(CLIENT_PATCH_TARGET, return_value=_mock_client(LinkupSourcedAnswer(answer="42", sources=[]))):
        message = component.linkup_sourced_answer()
    assert message.text == "42"


def test_api_errors_propagate(component):
    """SDK errors surface to the caller instead of being swallowed."""
    client = MagicMock()
    client.search.side_effect = RuntimeError("boom")
    with patch(CLIENT_PATCH_TARGET, return_value=client), pytest.raises(RuntimeError, match="boom"):
        component.linkup_search()


def test_tool_mode_exposes_linkup_specific_tools():
    """Each output becomes a tool whose name does not collide with other search components."""
    # Tools read inputs the way a graph sets them (constructor kwargs), not
    # attributes assigned after construction, so build the component directly.
    component = LinkupSearchComponent(
        linkup_api_key="test-key", depth="standard", max_results=5
    )  # pragma: allowlist secret
    tools = asyncio.run(component.to_toolkit())
    assert [tool.name for tool in tools] == ["linkup_search", "linkup_sourced_answer"]

    client = _mock_client(SOURCED_ANSWER)
    with patch(CLIENT_PATCH_TARGET, return_value=client):
        output = asyncio.run(tools[1].ainvoke({"query": "what is langflow"}))
    assert client.search.call_args.args == ("what is langflow",)
    assert client.search.call_args.kwargs["max_results"] == 5
    assert "Langflow is a visual workflow builder." in str(output)
