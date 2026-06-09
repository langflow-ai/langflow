"""Unit tests for Semantic Scholar Citation Graph component."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx
from lfx.components.semanticscholar.citation_graph import CitationGraphComponent
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame

# Mocked API response with nested JSON and edge cases
MOCK_API_RESPONSE = {
    "data": [
        {
            "contexts": ["intro"],
            "intents": ["background"],
            "citingPaper": {
                "paperId": "c111",
                "title": "A Review of Attention",
                "year": 2020,
                "citationCount": 50,
                "isOpenAccess": True,
                "authors": [{"name": "Alice Scholar"}],
            },
        },
        {
            "contexts": ["method"],
            "intents": ["methodology"],
            "citingPaper": {
                "paperId": "c222",
                "title": "Improving Transformers",
                "year": 2021,
                "citationCount": 500,
                "isOpenAccess": False,
                "authors": [],  # Empty authors case
            },
        },
        {
            "citingPaper": None  # Edge case: missing paper info
        },
        {
            "contexts": [],
            "intents": [],
            "citingPaper": {
                "paperId": "c333",
                "title": "Low Impact Paper",
                "year": 2023,
                "citationCount": 2,
                "isOpenAccess": True,
                "authors": [{"name": "Charlie Postdoc"}],
            },
        },
    ],
    "next": None,
}

BASE_URL_REGEX = r".*/citations.*"


@pytest.mark.unit
class TestCitationGraphFetcher:
    """Test Semantic Scholar Citation Graph component logic."""

    # --- Input Validation ---

    @pytest.mark.asyncio
    async def test_citation_graph_empty_paper_id(self):
        """Tests validation when the paper ID is empty."""
        component = CitationGraphComponent()
        component.paper_id = ""

        results = await component.fetch_citations()

        assert len(results) == 1
        assert "error" in results[0].data
        assert "Paper ID empty or could not be extracted" in results[0].data["error"]

    @pytest.mark.asyncio
    @respx.mock
    async def test_citation_graph_smart_funnel_input(self):
        """Tests if the component correctly extracts paper_id from a Data list."""
        respx.get(url__regex=r".*/paper/smart_paper_777/citations.*").respond(status_code=200, json={"data": []})

        component = CitationGraphComponent()

        mock_data_list = [
            Data(data={"paper_id": "smart_paper_777", "title": "Main Target"}),
            Data(data={"paper_id": "other_paper_888"}),
        ]

        component.paper_data = mock_data_list
        component.max_results = 10

        await component.fetch_citations()

        # Ensures it extracted 'smart_paper_777' from the first element
        assert len(respx.calls) == 1
        assert "smart_paper_777" in str(respx.calls.last.request.url)

    @pytest.mark.asyncio
    async def test_citation_graph_empty_list_input(self):
        """Tests validation when input is an empty list."""
        component = CitationGraphComponent()
        component.paper_data = []
        component.max_results = 10

        results = await component.fetch_citations()

        assert "error" in results[0].data
        assert "Paper ID empty" in results[0].data["error"]

    @pytest.mark.asyncio
    @respx.mock
    async def test_citation_graph_id_stripping(self):
        """Tests if paper_id is stripped of whitespaces before network call."""
        respx.get(url__regex=r".*/clean_target_123/citations.*").respond(status_code=200, json={"data": []})

        component = CitationGraphComponent()
        component.paper_id = "  clean_target_123  "
        await component.fetch_citations()

        assert len(respx.calls) == 1

    # --- Parsing and Business Logic ---

    @pytest.mark.asyncio
    @respx.mock
    async def test_citation_graph_nested_json_parsing(self):
        """Tests 'citingPaper' extraction, field mapping and metadata (contexts/intents)."""
        respx.get(url__regex=BASE_URL_REGEX).respond(status_code=200, json=MOCK_API_RESPONSE)

        component = CitationGraphComponent()
        component.paper_id = "original_123"
        component.max_results = 10

        results = await component.fetch_citations()

        assert len(results) == 3
        # Check if mapped to correct internal keys (testing the most cited one due to sorting)
        top_paper = results[0].data
        assert top_paper["citing_paper_id"] == "c222"
        assert top_paper["is_open_access"] is False
        assert "methodology" in top_paper["citation_intents"]
        assert top_paper["authors"] == "Unknown"  # Checks fallback for empty authors

    @pytest.mark.asyncio
    @respx.mock
    async def test_citation_graph_sorting_by_citations(self):
        """Tests if local sorting correctly prioritizes highly cited papers."""
        respx.get(url__regex=BASE_URL_REGEX).respond(status_code=200, json=MOCK_API_RESPONSE)

        component = CitationGraphComponent()
        component.paper_id = "original_123"
        component.max_results = 10

        results = await component.fetch_citations()

        # Expected order: c222 (500), c111 (50), c333 (2)
        assert results[0].data["citation_count"] == 500
        assert results[1].data["citation_count"] == 50
        assert results[2].data["citation_count"] == 2

    @pytest.mark.asyncio
    @respx.mock
    async def test_citation_graph_max_results_limit(self):
        """Tests if the component halts exactly at max_results limit."""
        respx.get(url__regex=BASE_URL_REGEX).respond(status_code=200, json=MOCK_API_RESPONSE)

        component = CitationGraphComponent()
        component.paper_id = "original_123"
        component.max_results = 2

        results = await component.fetch_citations()

        # Even though mock has 3 valid papers, we only requested 2
        assert len(results) == 2

    @pytest.mark.asyncio
    @respx.mock
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_citation_graph_pagination_logic(self, mock_sleep):
        """Tests if offset advances correctly when 'next' is provided."""
        page_1 = {"data": [MOCK_API_RESPONSE["data"][0]], "next": 10}
        page_2 = {"data": [MOCK_API_RESPONSE["data"][1]], "next": None}

        route = respx.get(url__regex=BASE_URL_REGEX)
        route.side_effect = [httpx.Response(200, json=page_1), httpx.Response(200, json=page_2)]

        component = CitationGraphComponent()
        component.paper_id = "original_123"
        component.max_results = 5

        await component.fetch_citations()

        assert route.call_count == 2
        # Ensure offset=10 was injected into the URL params of the second request
        assert "offset=10" in str(route.calls[1].request.url)

        mock_sleep.assert_any_call(1)

    # --- Network and Resilience ---

    @pytest.mark.asyncio
    @respx.mock
    async def test_citation_graph_404_not_found(self):
        """Tests graceful handling of 404 paper not found."""
        respx.get(url__regex=BASE_URL_REGEX).respond(status_code=404)

        component = CitationGraphComponent()
        component.paper_id = "fake_id_999"

        results = await component.fetch_citations()

        assert len(results) == 1
        assert "error" in results[0].data
        assert "not found" in results[0].data["error"]

    @pytest.mark.asyncio
    @respx.mock
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_citation_graph_429_rate_limit_empty(self, mock_sleep):
        """Tests 429 rate limit when no papers have been fetched yet."""
        respx.get(url__regex=BASE_URL_REGEX).respond(status_code=429)

        component = CitationGraphComponent()
        component.paper_id = "original_123"

        results = await component.fetch_citations()

        assert len(results) == 1
        assert "error" in results[0].data
        assert "Rate limit" in results[0].data["error"]
        mock_sleep.assert_called()

    @pytest.mark.asyncio
    @respx.mock
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_citation_graph_429_rate_limit_partial(self, mock_sleep):
        """Tests 429 rate limit breaking the loop but returning already fetched papers."""
        page_1 = {"data": [MOCK_API_RESPONSE["data"][0]], "next": 10}

        route = respx.get(url__regex=BASE_URL_REGEX)
        route.side_effect = [httpx.Response(200, json=page_1), httpx.Response(429)]

        component = CitationGraphComponent()
        component.paper_id = "original_123"
        component.max_results = 5

        results = await component.fetch_citations()

        # It should not return an error, but rather the 1 paper it managed to fetch
        assert len(results) == 1
        assert "error" not in results[0].data
        assert results[0].data["citing_paper_id"] == "c111"
        mock_sleep.assert_called()

    @pytest.mark.asyncio
    @respx.mock
    async def test_citation_graph_http_status_error(self):
        """Tests handling of generic server errors (500)."""
        respx.get(url__regex=BASE_URL_REGEX).respond(status_code=500, text="Internal Server Error")

        component = CitationGraphComponent()
        component.paper_id = "original_123"

        results = await component.fetch_citations()

        assert len(results) == 1
        assert "error" in results[0].data
        assert "HTTP Error 500" in results[0].data["error"]

    # --- Outputs ---

    @pytest.mark.asyncio
    @respx.mock
    async def test_citation_graph_dataframe_output(self):
        """Tests the alternative DataFrame output method."""
        respx.get(url__regex=BASE_URL_REGEX).respond(status_code=200, json={"data": []})

        component = CitationGraphComponent()
        component.paper_id = "original_123"

        df = await component.fetch_citations_dataframe()
        assert isinstance(df, DataFrame)
