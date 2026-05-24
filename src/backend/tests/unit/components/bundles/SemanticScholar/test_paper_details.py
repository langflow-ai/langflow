"""Unit tests for Semantic Scholar Paper Details component."""

from unittest.mock import AsyncMock, patch

import pytest
import respx
from lfx.components.semanticscholar.paper_details import PaperDetailsComponent
from lfx.schema.artifact import Data
from lfx.schema.dataframe import DataFrame

# Deep metadata mock
MOCK_API_RESPONSE = {
    "paperId": "12345abcd",
    "title": "A Comprehensive Guide to Everything",
    "abstract": "This paper explains the universe.",
    "tldr": {"model": "tldr@2.0.0", "text": "The universe is big and complex."},
    "year": 2024,
    "publicationDate": "2024-05-11",
    "venue": "Nature",
    "citationCount": 42,
    "isOpenAccess": True,
    "openAccessPdf": {"url": "https://example.com/paper.pdf", "status": "GREEN"},
    "authors": [{"name": "Jane Doe"}],
    "url": "https://semanticscholar.org/paper/12345abcd",
}

# Edge case mock (missing nested fields)
MOCK_API_RESPONSE_EMPTY = {
    "paperId": "99999",
    "title": "Minimal Paper",
    "abstract": None,
    "tldr": None,
    "isOpenAccess": False,
    "openAccessPdf": None,
    "authors": [],
}

BASE_URL_REGEX = r".*/paper/.*"


@pytest.mark.unit
class TestPaperDetailsFetcher:
    """Test Semantic Scholar Paper Details component logic."""

    # --- Validation ---

    @pytest.mark.asyncio
    async def test_paper_details_empty_id(self):
        """Tests validation when paper_id is empty."""
        component = PaperDetailsComponent()
        component.paper_id = "   "
        results = await component.fetch_details()
        assert "error" in results[0].data
        assert "Paper ID empty or could not be extracted" in results[0].data["error"]

    @pytest.mark.asyncio
    @respx.mock
    async def test_paper_details_smart_funnel_input(self):
        """Tests if the component correctly extracts paper_id from a Data list."""
        respx.get(url__regex=r".*/paper/smart_details_777.*").respond(status_code=200, json=MOCK_API_RESPONSE)

        component = PaperDetailsComponent()

        mock_data_list = [
            Data(data={"paper_id": "smart_details_777", "title": "Deep Dive Paper"}),
            Data(data={"paper_id": "other_paper_888"}),
        ]

        component.paper_data = mock_data_list

        results = await component.fetch_details()

        assert "error" not in results[0].data, f"Internal Error: {results[0].data.get('error')}"
        assert len(respx.calls) == 1
        assert "smart_details_777" in str(respx.calls.last.request.url)

    @pytest.mark.asyncio
    async def test_paper_details_empty_list_input(self):
        """Tests validation when input is an empty list."""
        component = PaperDetailsComponent()
        component.paper_data = []

        results = await component.fetch_details()

        assert "error" in results[0].data
        assert "Paper ID empty or could not be extracted" in results[0].data["error"]

    @pytest.mark.asyncio
    @respx.mock
    async def test_paper_details_id_stripping(self):
        """Tests if paper_id is stripped correctly before API call."""
        respx.get(url__regex=r".*/paper/clean_id_123.*").respond(status_code=200, json=MOCK_API_RESPONSE)

        component = PaperDetailsComponent()
        component.paper_id = "  clean_id_123  "
        await component.fetch_details()
        assert len(respx.calls) == 1

    # --- Logic & Parsing ---

    @pytest.mark.asyncio
    @respx.mock
    async def test_paper_details_parsing_success(self):
        """Tests standard parsing including nested tldr and pdf_url."""
        respx.get(url__regex=BASE_URL_REGEX).respond(status_code=200, json=MOCK_API_RESPONSE)

        component = PaperDetailsComponent()
        component.paper_id = "12345abcd"

        results = await component.fetch_details()
        assert len(results) == 1

        data = results[0].data
        assert data["title"] == "A Comprehensive Guide to Everything"
        assert data["tldr"] == "The universe is big and complex."
        assert data["pdf_url"] == "https://example.com/paper.pdf"
        assert data["venue"] == "Nature"

    @pytest.mark.asyncio
    @respx.mock
    async def test_paper_details_fallbacks(self):
        """Tests behavior when tldr, abstract, and openAccessPdf are null."""
        respx.get(url__regex=BASE_URL_REGEX).respond(status_code=200, json=MOCK_API_RESPONSE_EMPTY)

        component = PaperDetailsComponent()
        component.paper_id = "99999"

        results = await component.fetch_details()
        data = results[0].data

        assert data["tldr"] == "No TLDR available."
        assert data["abstract"] == "No abstract available."
        assert data["pdf_url"] is None
        assert data["authors"] == "Unknown"

    # --- Resilience ---

    @pytest.mark.asyncio
    @respx.mock
    async def test_paper_details_404_not_found(self):
        """Tests handling of invalid or non-existent paper IDs."""
        respx.get(url__regex=BASE_URL_REGEX).respond(status_code=404)

        component = PaperDetailsComponent()
        component.paper_id = "fake_id"

        results = await component.fetch_details()
        assert "not found" in results[0].data["error"].lower()

    @pytest.mark.asyncio
    @respx.mock
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_paper_details_429_rate_limit(self, mock_sleep):
        """Tests HTTP 429 triggers the defense sleep and returns an error."""
        respx.get(url__regex=BASE_URL_REGEX).respond(status_code=429)

        component = PaperDetailsComponent()
        component.paper_id = "12345abcd"

        results = await component.fetch_details()

        assert "Rate limit" in results[0].data["error"]
        mock_sleep.assert_called_once_with(2)

    @pytest.mark.asyncio
    @respx.mock
    async def test_paper_details_http_error(self):
        """Tests handling of generic server errors."""
        respx.get(url__regex=BASE_URL_REGEX).respond(status_code=500, text="Internal Error")

        component = PaperDetailsComponent()
        component.paper_id = "123"

        results = await component.fetch_details()
        assert "HTTP Error 500" in results[0].data["error"]

    # --- DataFrame ---

    @pytest.mark.asyncio
    @respx.mock
    async def test_paper_details_dataframe_output(self):
        """Tests if the method returns a valid DataFrame object."""
        respx.get(url__regex=BASE_URL_REGEX).respond(status_code=200, json=MOCK_API_RESPONSE)

        component = PaperDetailsComponent()
        component.paper_id = "123"

        df = await component.fetch_details_dataframe()
        assert isinstance(df, DataFrame)
