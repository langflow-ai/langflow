"""Unit tests for Semantic Scholar Search component."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx
from lfx.components.semanticscholar.search_papers import SemanticScholarSearchComponent
from lfx.schema.dataframe import DataFrame

# Comprehensive Mock API response including edge cases
MOCK_API_RESPONSE = {
    "data": [
        {
            "paperId": "111",
            "title": "Attention Is All You Need",
            "year": 2017,
            "citationCount": 100000,
            "isOpenAccess": True,
            "authors": [{"name": "Ashish Vaswani"}],
        },
        {
            "paperId": "222",
            "title": "Paper Without Abstract",
            "year": 2023,
            "citationCount": 2,
            "isOpenAccess": False,
            "abstract": None,  # Edge case
            "authors": [],  # Edge case
        },
        {
            "paperId": "333",
            "title": "Unknown Year Paper",
            "year": None,  # Edge case
            "citationCount": 50,
            "isOpenAccess": True,
            "authors": [{"name": "Jane Smith"}],
        },
    ],
    "next": None,
}

BASE_URL = "https://api.semanticscholar.org/graph/v1/paper/search"


@pytest.mark.unit
class TestSemanticScholarSearch:
    """Test Semantic Scholar Search component logic and filters."""

    # --- Input Validation ---

    async def test_search_papers_empty_query(self):
        """Tests validation when the search query is empty."""
        component = SemanticScholarSearchComponent()
        component.search_query = ""
        results = await component.search_papers()
        assert len(results) == 1
        assert "error" in results[0].data

    async def test_search_papers_invalid_year_format(self):
        """Tests validation when the year format is incorrect."""
        component = SemanticScholarSearchComponent()
        component.search_query = "AI"
        component.year_filter = "invalid_year"
        results = await component.search_papers()
        assert "error" in results[0].data

    # --- Business Logic & Filters ---

    @respx.mock
    async def test_search_papers_edge_cases_handling(self):
        """Tests missing abstracts, empty authors, and None years fallback mapping."""
        respx.get(BASE_URL).respond(status_code=200, json=MOCK_API_RESPONSE)

        component = SemanticScholarSearchComponent()
        component.search_query = "AI"
        component.max_results = 10

        results = await component.search_papers()

        by_id = {r.data["paper_id"]: r.data for r in results}

        # Check fallbacks using specific IDs
        assert by_id["222"]["abstract"] == "No abstract available."
        assert by_id["222"]["authors"] == "Unknown"
        assert by_id["333"]["year"] is None

    @respx.mock
    async def test_search_papers_open_access_filter(self):
        """Tests if the Open Access filter strictly removes non-OA papers."""
        respx.get(BASE_URL).respond(status_code=200, json=MOCK_API_RESPONSE)

        component = SemanticScholarSearchComponent()
        component.search_query = "AI"
        component.max_results = 10
        component.only_open_access = True

        results = await component.search_papers()

        # Papers 111 and 333 are OA
        assert len(results) == 2
        assert "222" not in [r.data["paper_id"] for r in results]

    @respx.mock
    async def test_search_papers_min_citations_filter(self):
        """Tests if papers with citations below the threshold are discarded."""
        respx.get(BASE_URL).respond(status_code=200, json=MOCK_API_RESPONSE)

        component = SemanticScholarSearchComponent()
        component.search_query = "AI"
        component.max_results = 10
        component.min_citations = 10

        results = await component.search_papers()

        # Paper 222 (2 citations) should be removed
        assert len(results) == 2
        assert "222" not in [r.data["paper_id"] for r in results]

    @respx.mock
    async def test_search_papers_combined_filters(self):
        """Tests Open Access and Min Citations simultaneously."""
        respx.get(BASE_URL).respond(status_code=200, json=MOCK_API_RESPONSE)

        component = SemanticScholarSearchComponent()
        component.search_query = "AI"
        component.max_results = 10
        component.only_open_access = True
        component.min_citations = 10

        results = await component.search_papers()

        # Papers 111 (OA, 100000 cit.) and 333 (OA, 50 cit.) meet both criteria
        assert len(results) == 2

    @respx.mock
    async def test_search_papers_max_results_limit(self):
        """Tests if the component halts and slices the list exactly at max_results."""
        respx.get(BASE_URL).respond(status_code=200, json=MOCK_API_RESPONSE)

        component = SemanticScholarSearchComponent()
        component.search_query = "AI"
        component.max_results = 2  # Mock has 3

        results = await component.search_papers()

        assert len(results) == 2

    # --- Sorting ---

    @respx.mock
    async def test_search_papers_sorting_by_citations(self):
        """Tests Highest Citations sorting."""
        respx.get(BASE_URL).respond(status_code=200, json=MOCK_API_RESPONSE)

        component = SemanticScholarSearchComponent()
        component.search_query = "AI"
        component.max_results = 10
        component.sort_by = "Highest Citations"

        results = await component.search_papers()

        assert results[0].data["citation_count"] == 100000
        assert results[1].data["citation_count"] == 50
        assert results[2].data["citation_count"] == 2

    @respx.mock
    async def test_search_papers_sorting_newest(self):
        """Tests Newest First sorting, ensuring None years are handled gracefully."""
        respx.get(BASE_URL).respond(status_code=200, json=MOCK_API_RESPONSE)

        component = SemanticScholarSearchComponent()
        component.search_query = "AI"
        component.max_results = 10
        component.sort_by = "Newest First"

        results = await component.search_papers()

        # 2023 -> 2017 -> None (mapped to 0)
        assert results[0].data["year"] == 2023
        assert results[1].data["year"] == 2017
        assert results[2].data["year"] is None

    # --- Network, Pagination & Resilience ---

    @respx.mock
    async def test_search_papers_empty_api_response(self):
        """Tests component behavior when API finds no papers."""
        respx.get(BASE_URL).respond(status_code=200, json={"data": [], "next": None})

        component = SemanticScholarSearchComponent()
        component.search_query = "Super Obscure Topic"
        component.max_results = 10

        results = await component.search_papers()

        assert len(results) == 0

    @respx.mock
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_search_papers_pagination_offset(self, mock_sleep):
        """Tests if the next offset is requested across loop iterations."""
        page_1 = {"data": [MOCK_API_RESPONSE["data"][0]], "next": 100}
        page_2 = {"data": [MOCK_API_RESPONSE["data"][1]], "next": None}

        route = respx.get(BASE_URL)
        route.side_effect = [httpx.Response(200, json=page_1), httpx.Response(200, json=page_2)]

        component = SemanticScholarSearchComponent()
        component.search_query = "AI"
        component.max_results = 2

        results = await component.search_papers()

        assert len(results) == 2
        assert route.call_count == 2

        mock_sleep.assert_any_call(1)

    @respx.mock
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_search_papers_rate_limit_429(self, mock_sleep):
        """Tests if the component handles HTTP 429 rate limits gracefully."""
        respx.get(BASE_URL).respond(status_code=429)

        component = SemanticScholarSearchComponent()
        component.search_query = "AI"
        component.max_results = 10

        results = await component.search_papers()

        assert len(results) == 1
        assert "error" in results[0].data
        assert "Rate limit reached" in results[0].data["error"]
        mock_sleep.assert_called_once_with(2)

    @respx.mock
    async def test_search_papers_api_error_handling(self):
        """Tests generic API or network failure handling."""
        respx.get(BASE_URL).mock(side_effect=httpx.ConnectError("Network Error"))

        component = SemanticScholarSearchComponent()
        component.search_query = "AI"
        component.max_results = 10

        results = await component.search_papers()

        assert len(results) == 1
        assert "error" in results[0].data

    # --- DataFrame Output ---

    @respx.mock
    async def test_search_papers_dataframe_output(self):
        """Tests if the secondary method returns a valid DataFrame."""
        respx.get(BASE_URL).respond(status_code=200, json=MOCK_API_RESPONSE)

        component = SemanticScholarSearchComponent()
        component.search_query = "AI"
        component.max_results = 10

        df = await component.search_papers_dataframe()

        assert isinstance(df, DataFrame)
