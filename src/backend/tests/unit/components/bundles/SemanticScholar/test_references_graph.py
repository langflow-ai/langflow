"""Unit tests for Semantic Scholar Reference Graph component."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx
from lfx.components.semanticscholar.references_graph import ReferenceGraphComponent
from lfx.schema.dataframe import Data, DataFrame

MOCK_API_RESPONSE = {
    "data": [
        {
            "citedPaper": {
                "paperId": "r111",
                "title": "Foundation Paper A",
                "year": 2010,
                "citationCount": 5000,
                "isOpenAccess": True,
                "authors": [{"name": "Classic Author"}],
            }
        },
        {
            "citedPaper": {
                "paperId": "r222",
                "title": "Supporting Study B",
                "year": 2015,
                "citationCount": 100,
                "isOpenAccess": False,
                "authors": [],  # Edge case: empty authors
            }
        },
        {
            "citedPaper": None  # Edge case: missing paper info
        },
    ],
    "next": None,
}

BASE_URL_REGEX = r".*/references.*"


@pytest.mark.unit
class TestReferenceGraphFetcher:
    """Test Semantic Scholar Reference Graph component logic."""

    # --- Validation and Setup ---

    @pytest.mark.asyncio
    async def test_reference_graph_empty_id(self):
        """Tests validation when paper_id is empty."""
        component = ReferenceGraphComponent()
        component.paper_id = ""
        results = await component.fetch_references()
        assert "error" in results[0].data
        assert "Paper ID empty or could not be extracted" in results[0].data["error"]

    @pytest.mark.asyncio
    @respx.mock
    async def test_references_graph_smart_funnel_input(self):
        """Tests if the component correctly extracts paper_id from a Data list."""
        respx.get(url__regex=r".*/paper/smart_ref_777/references.*").respond(status_code=200, json={"data": []})

        component = ReferenceGraphComponent()

        mock_data_list = [
            Data(data={"paper_id": "smart_ref_777", "title": "Main Target"}),
            Data(data={"paper_id": "other_paper_888"}),
        ]

        component.paper_data = mock_data_list
        component.max_results = 10

        await component.fetch_references()

        assert len(respx.calls) == 1
        assert "smart_ref_777" in str(respx.calls.last.request.url)

    @pytest.mark.asyncio
    async def test_references_graph_empty_list_input(self):
        """Tests validation when input is an empty list."""
        component = ReferenceGraphComponent()
        component.paper_data = []
        component.max_results = 10

        results = await component.fetch_references()

        assert "error" in results[0].data
        assert "could not be extracted" in results[0].data["error"]

    @pytest.mark.asyncio
    @respx.mock
    async def test_reference_graph_id_stripping(self):
        """Tests if paper_id is correctly stripped of whitespace."""
        respx.get(url__regex=r".*/target_abc/references.*").respond(status_code=200, json={"data": []})

        component = ReferenceGraphComponent()
        component.paper_id = "  target_abc  "
        await component.fetch_references()

        assert len(respx.calls) == 1

    # --- Parsing and Business Logic ---

    @pytest.mark.asyncio
    @respx.mock
    async def test_reference_graph_cited_paper_parsing(self):
        """Tests 'citedPaper' extraction, None filtering, and mapping."""
        respx.get(url__regex=BASE_URL_REGEX).respond(status_code=200, json=MOCK_API_RESPONSE)

        component = ReferenceGraphComponent()
        component.paper_id = "source_123"
        component.max_results = 5

        results = await component.fetch_references()

        # Ensures None entry is skipped
        assert len(results) == 2

        by_id = {r.data["referenced_paper_id"]: r.data for r in results}

        assert by_id["r111"]["source_paper_id"] == "source_123"
        assert by_id["r111"]["is_open_access"] is True
        assert by_id["r222"]["authors"] == "Unknown"

    @pytest.mark.asyncio
    @respx.mock
    async def test_reference_graph_sorting_by_impact(self):
        """Tests if references are sorted by citation count locally."""
        respx.get(url__regex=BASE_URL_REGEX).respond(status_code=200, json=MOCK_API_RESPONSE)

        component = ReferenceGraphComponent()
        component.paper_id = "target_abc"
        component.max_results = 10

        results = await component.fetch_references()

        # 5000 citations should appear before 100
        assert results[0].data["citation_count"] == 5000
        assert results[1].data["citation_count"] == 100

    @pytest.mark.asyncio
    @respx.mock
    async def test_reference_graph_max_results_respected(self):
        """Tests if the component cuts off exactly at max_results limit."""
        respx.get(url__regex=BASE_URL_REGEX).respond(status_code=200, json=MOCK_API_RESPONSE)

        component = ReferenceGraphComponent()
        component.paper_id = "target_abc"
        component.max_results = 1

        results = await component.fetch_references()
        assert len(results) == 1

    @pytest.mark.asyncio
    @respx.mock
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_reference_graph_pagination(self, mock_sleep):
        """Tests if pagination logic requests subsequent offsets."""
        page_1 = {"data": [MOCK_API_RESPONSE["data"][0]], "next": 50}
        page_2 = {"data": [MOCK_API_RESPONSE["data"][1]], "next": None}

        route = respx.get(url__regex=BASE_URL_REGEX)
        route.side_effect = [httpx.Response(200, json=page_1), httpx.Response(200, json=page_2)]

        component = ReferenceGraphComponent()
        component.paper_id = "target_abc"
        component.max_results = 2

        results = await component.fetch_references()

        assert len(results) == 2
        assert route.call_count == 2
        assert "offset=50" in str(route.calls[1].request.url)

        mock_sleep.assert_any_call(1)

    # --- Error Handling and Resilience ---

    @pytest.mark.asyncio
    @respx.mock
    async def test_reference_graph_404_handling(self):
        """Tests behavior when the target paper ID is not found."""
        respx.get(url__regex=BASE_URL_REGEX).respond(status_code=404)

        component = ReferenceGraphComponent()
        component.paper_id = "invalid_id"

        results = await component.fetch_references()
        assert "not found" in results[0].data["error"].lower()

    @pytest.mark.asyncio
    @respx.mock
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_reference_graph_rate_limit_empty(self, mock_sleep):
        """Tests HTTP 429 handling on initial request."""
        respx.get(url__regex=BASE_URL_REGEX).respond(status_code=429)

        component = ReferenceGraphComponent()
        component.paper_id = "target_abc"

        results = await component.fetch_references()

        assert "Rate limit" in results[0].data["error"]
        mock_sleep.assert_called_once_with(2)

    @pytest.mark.asyncio
    @respx.mock
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_reference_graph_rate_limit_partial(self, mock_sleep):
        """Tests HTTP 429 returns already fetched papers instead of failing completely."""
        page_1 = {"data": [MOCK_API_RESPONSE["data"][0]], "next": 10}

        route = respx.get(url__regex=BASE_URL_REGEX)
        route.side_effect = [httpx.Response(200, json=page_1), httpx.Response(429)]

        component = ReferenceGraphComponent()
        component.paper_id = "target_abc"
        component.max_results = 5

        results = await component.fetch_references()

        assert len(results) == 1
        assert "error" not in results[0].data
        mock_sleep.assert_any_call(2)

    @pytest.mark.asyncio
    @respx.mock
    async def test_reference_graph_http_error(self):
        """Tests handling of generic server errors."""
        respx.get(url__regex=BASE_URL_REGEX).respond(status_code=500, text="Internal Server Error")

        component = ReferenceGraphComponent()
        component.paper_id = "target_abc"

        results = await component.fetch_references()
        assert "HTTP Error 500" in results[0].data["error"]

    # --- DataFrame Output ---

    @pytest.mark.asyncio
    @respx.mock
    async def test_reference_graph_dataframe_output(self):
        """Tests the DataFrame conversion output."""
        respx.get(url__regex=BASE_URL_REGEX).respond(status_code=200, json={"data": []})

        component = ReferenceGraphComponent()
        component.paper_id = "target_abc"

        df = await component.fetch_references_dataframe()
        assert isinstance(df, DataFrame)
