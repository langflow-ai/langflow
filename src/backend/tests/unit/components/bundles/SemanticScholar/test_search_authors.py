"""Unit tests for Semantic Scholar Author Search component."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx
from lfx.components.semanticscholar.search_authors import SearchAuthorsComponent
from lfx.schema.dataframe import DataFrame

MOCK_API_RESPONSE = {
    "data": [
        {
            "authorId": "1440621",
            "name": "Andrew Ng",
            "affiliations": ["Stanford University", "DeepLearning.AI"],
            "paperCount": 500,
            "citationCount": 300000,
            "hIndex": 150,
            "url": "https://semanticscholar.org/author/1440621",
        },
        {
            "authorId": "99999",
            "name": "Another Andrew",
            "affiliations": [],  # Edge case: empty affiliations
            "paperCount": 2,
            "citationCount": 10,
            "hIndex": 1,
            "url": "https://semanticscholar.org/author/99999",
        },
    ],
    "next": None,
}

BASE_URL = "https://api.semanticscholar.org/graph/v1/author/search"


@pytest.mark.unit
class TestSearchAuthorsFetcher:
    """Test Semantic Scholar Author Search component logic."""

    # --- Validation ---

    @pytest.mark.asyncio
    async def test_search_authors_empty_query(self):
        """Tests validation when search query is empty."""
        component = SearchAuthorsComponent()
        component.search_query = "   "
        component.max_results = 10
        results = await component.search_authors()
        assert "error" in results[0].data

    # --- Logic & Parsing ---

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_authors_parsing_and_fallbacks(self):
        """Tests correct mapping and empty list fallbacks for affiliations."""
        respx.get(BASE_URL).respond(status_code=200, json=MOCK_API_RESPONSE)

        component = SearchAuthorsComponent()
        component.search_query = "Andrew"
        component.max_results = 10

        results = await component.search_authors()
        assert len(results) == 2

        by_id = {r.data["author_id"]: r.data for r in results}

        # Test array joining
        assert by_id["1440621"]["affiliations"] == "Stanford University, DeepLearning.AI"

        # Test empty array fallback
        assert by_id["99999"]["affiliations"] == "Unknown Affiliation"

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_authors_sorting_by_hindex(self):
        """Tests if the authors are sorted by h-index locally."""
        respx.get(BASE_URL).respond(status_code=200, json=MOCK_API_RESPONSE)

        component = SearchAuthorsComponent()
        component.search_query = "Andrew"
        component.max_results = 10

        results = await component.search_authors()

        # hIndex 150 must come before hIndex 1
        assert results[0].data["h_index"] == 150
        assert results[1].data["h_index"] == 1

    @pytest.mark.asyncio
    @respx.mock
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_search_authors_pagination(self, mock_sleep):
        """Tests pagination offset request and failsafe delay."""
        page_1 = {"data": [MOCK_API_RESPONSE["data"][0]], "next": 50}
        page_2 = {"data": [MOCK_API_RESPONSE["data"][1]], "next": None}

        route = respx.get(BASE_URL)
        route.side_effect = [httpx.Response(200, json=page_1), httpx.Response(200, json=page_2)]

        component = SearchAuthorsComponent()
        component.search_query = "Andrew"
        component.max_results = 5

        await component.search_authors()

        assert route.call_count == 2
        assert "offset=50" in str(route.calls[1].request.url)
        mock_sleep.assert_any_call(1)

    # --- Network Resilience ---

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_authors_empty_api_response(self):
        """Tests component behavior when no authors match the query."""
        respx.get(BASE_URL).respond(status_code=200, json={"data": [], "next": None})

        component = SearchAuthorsComponent()
        component.search_query = "ObscureNameNoOneHas"
        component.max_results = 10

        results = await component.search_authors()
        assert len(results) == 0

    @pytest.mark.asyncio
    @respx.mock
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_search_authors_429_rate_limit(self, mock_sleep):
        """Tests HTTP 429 handling, ensuring defense mechanisms trigger."""
        respx.get(BASE_URL).respond(status_code=429)

        component = SearchAuthorsComponent()
        component.search_query = "Andrew"
        component.max_results = 10

        results = await component.search_authors()

        assert "Rate limit" in results[0].data["error"]
        mock_sleep.assert_any_call(2)

    @pytest.mark.asyncio
    @respx.mock
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_search_authors_429_rate_limit_partial(self, mock_sleep):
        """Tests HTTP 429 returns already fetched authors instead of failing completely."""
        page_1 = {"data": [MOCK_API_RESPONSE["data"][0]], "next": 100}

        route = respx.get(BASE_URL)
        route.side_effect = [httpx.Response(200, json=page_1), httpx.Response(429)]

        component = SearchAuthorsComponent()
        component.search_query = "Andrew"
        component.max_results = 5

        results = await component.search_authors()

        # Ensures it returns the first author successfully instead of a fatal error
        assert len(results) == 1
        assert "error" not in results[0].data
        assert results[0].data["author_id"] == "1440621"

        # Ensures the 2-second defense delay was activated
        mock_sleep.assert_any_call(2)

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_authors_http_error(self):
        """Tests generic 500 server error handling."""
        respx.get(BASE_URL).respond(status_code=500, text="Server Fault")

        component = SearchAuthorsComponent()
        component.search_query = "Andrew"
        component.max_results = 10

        results = await component.search_authors()
        assert "HTTP Error 500" in results[0].data["error"]

    # --- DataFrame ---

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_authors_dataframe_output(self):
        """Tests DataFrame conversion."""
        respx.get(BASE_URL).respond(status_code=200, json={"data": []})

        component = SearchAuthorsComponent()
        component.search_query = "Andrew"

        # Test the correct method name
        df = await component.search_authors_dataframe()
        assert isinstance(df, DataFrame)
