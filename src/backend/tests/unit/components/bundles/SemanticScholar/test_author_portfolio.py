"""Unit tests for Semantic Scholar Author Portfolio component."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx
from lfx.components.semanticscholar.author_portfolio import AuthorPortfolioComponent
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame

MOCK_API_RESPONSE = {
    "data": [
        {
            "paperId": "a111",
            "title": "Deep Learning Tutorial",
            "year": 2015,
            "citationCount": 20000,
            "isOpenAccess": True,
            "abstract": "A comprehensive guide to deep learning.",
            "authors": [{"name": "John Author"}, {"name": "Jane Coauthor"}],
        },
        {
            "paperId": "a222",
            "title": "Minor Workshop Paper",
            "year": 2016,
            "citationCount": 5,
            "isOpenAccess": False,
            "abstract": None,  # Edge case
            "authors": [],  # Edge case
        },
    ],
    "next": None,
}

BASE_URL_REGEX = r".*/author/.*/papers.*"


@pytest.mark.unit
class TestAuthorPortfolioFetcher:
    """Test Semantic Scholar Author Portfolio component logic."""

    # --- Validation and Setup ---

    async def test_author_portfolio_empty_id(self):
        """Tests validation when author_id is empty."""
        component = AuthorPortfolioComponent()
        component.author_id = "   "
        component.max_results = 10
        results = await component.fetch_portfolio()
        assert "error" in results[0].data
        assert "could not be extracted" in results[0].data["error"]

    @respx.mock
    async def test_author_portfolio_id_stripping(self):
        """Tests if author_id is stripped correctly before API call."""
        respx.get(url__regex=r".*/author/1440621/papers.*").respond(status_code=200, json={"data": []})

        component = AuthorPortfolioComponent()
        component.author_id = "  1440621  "
        await component.fetch_portfolio()
        assert len(respx.calls) == 1

    # --- Parsing, Sorting and Logic ---

    @respx.mock
    async def test_author_portfolio_parsing_and_fallbacks(self):
        """Tests general parsing and missing fields fallback."""
        respx.get(url__regex=BASE_URL_REGEX).respond(status_code=200, json=MOCK_API_RESPONSE)

        component = AuthorPortfolioComponent()
        component.author_id = "123"
        component.max_results = 10

        results = await component.fetch_portfolio()

        assert len(results) == 2

        by_id = {r.data["paper_id"]: r.data for r in results}

        assert by_id["a111"]["author_id"] == "123"
        assert by_id["a222"]["author_id"] == "123"

        # Check normal fields
        assert by_id["a111"]["citation_count"] == 20000
        assert by_id["a111"]["authors"] == "John Author, Jane Coauthor"

        # Check fallbacks
        assert by_id["a222"]["abstract"] == "No abstract available."
        assert by_id["a222"]["authors"] == "Unknown"

    @respx.mock
    async def test_author_portfolio_sorting(self):
        """Tests if the author's papers are sorted by citation count."""
        respx.get(url__regex=BASE_URL_REGEX).respond(status_code=200, json=MOCK_API_RESPONSE)

        component = AuthorPortfolioComponent()
        component.author_id = "123"
        component.max_results = 10

        results = await component.fetch_portfolio()

        # 20000 citations should come before 5
        assert results[0].data["citation_count"] == 20000
        assert results[1].data["citation_count"] == 5

    @respx.mock
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_author_portfolio_pagination(self, mock_sleep):
        """Tests pagination logic and offset requests."""
        page_1 = {"data": [MOCK_API_RESPONSE["data"][0]], "next": 100}
        page_2 = {"data": [MOCK_API_RESPONSE["data"][1]], "next": None}

        route = respx.get(url__regex=BASE_URL_REGEX)
        route.side_effect = [httpx.Response(200, json=page_1), httpx.Response(200, json=page_2)]

        component = AuthorPortfolioComponent()
        component.author_id = "123"
        component.max_results = 5

        results = await component.fetch_portfolio()

        assert len(results) == 2
        assert route.call_count == 2
        assert "offset=100" in str(route.calls[1].request.url)

        # Verify pagination sleep delay
        mock_sleep.assert_any_call(1)

    # --- Error Handling and Resilience ---

    @respx.mock
    async def test_author_portfolio_404_not_found(self):
        """Tests graceful handling when author does not exist."""
        respx.get(url__regex=BASE_URL_REGEX).respond(status_code=404)

        component = AuthorPortfolioComponent()
        component.author_id = "ghost_author"

        results = await component.fetch_portfolio()
        assert "not found" in results[0].data["error"].lower()

    @respx.mock
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_author_portfolio_429_rate_limit(self, mock_sleep):
        """Tests HTTP 429 rate limit triggers sleep and returns partial data."""
        page_1 = {"data": [MOCK_API_RESPONSE["data"][0]], "next": 100}

        route = respx.get(url__regex=BASE_URL_REGEX)
        route.side_effect = [httpx.Response(200, json=page_1), httpx.Response(429)]

        component = AuthorPortfolioComponent()
        component.author_id = "123"
        component.max_results = 5

        results = await component.fetch_portfolio()

        assert len(results) == 1
        assert "error" not in results[0].data
        # Ensures the 429 defense delay was activated
        mock_sleep.assert_any_call(2)

    @respx.mock
    async def test_author_portfolio_http_error(self):
        """Tests handling of generic server errors."""
        respx.get(url__regex=BASE_URL_REGEX).respond(status_code=500, text="Internal Error")

        component = AuthorPortfolioComponent()
        component.author_id = "123"

        results = await component.fetch_portfolio()
        assert "HTTP Error 500" in results[0].data["error"]

    # --- DataFrame Output ---

    @respx.mock
    async def test_author_portfolio_dataframe_output(self):
        """Tests if the method returns a valid DataFrame object."""
        respx.get(url__regex=BASE_URL_REGEX).respond(status_code=200, json={"data": []})

        component = AuthorPortfolioComponent()
        component.author_id = "123"

        df = await component.fetch_portfolio_dataframe()
        assert isinstance(df, DataFrame)

    @respx.mock
    async def test_author_portfolio_smart_funnel_input(self):
        """Tests if the component correctly extracts author_id from a Data list."""
        respx.get(url__regex=r".*/author/smart_id_777/papers.*").respond(status_code=200, json={"data": []})

        component = AuthorPortfolioComponent()

        mock_data_list = [
            Data(data={"author_id": "smart_id_777", "name": "Primary Author"}),
            Data(data={"author_id": "other_id_888", "name": "Secondary Author"}),
        ]

        component.author_data = mock_data_list
        component.max_results = 10

        await component.fetch_portfolio()

        # Ensures it extracted 'smart_id_777' from the first element and successfully called the API
        assert len(respx.calls) == 1
        assert "smart_id_777" in str(respx.calls.last.request.url)

    async def test_author_portfolio_empty_list_input(self):
        """Tests validation when input is an empty list."""
        component = AuthorPortfolioComponent()
        component.author_data = []
        component.max_results = 10
        results = await component.fetch_portfolio()
        assert "error" in results[0].data
        assert "could not be extracted" in results[0].data["error"]
