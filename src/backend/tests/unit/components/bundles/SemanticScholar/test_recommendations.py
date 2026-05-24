"""Unit tests for Semantic Scholar AI Recommendations component."""

from unittest.mock import AsyncMock, patch

import pytest
import respx
from lfx.components.semanticscholar.recommendations import AIRecommendationsComponent
from lfx.schema.artifact import Data
from lfx.schema.dataframe import DataFrame

MOCK_API_RESPONSE = {
    "recommendedPapers": [
        {
            "paperId": "rec111",
            "title": "Highly Relevant Paper",
            "year": 2022,
            "citationCount": 80,
            "isOpenAccess": True,
            "authors": [{"name": "AI Researcher"}],
        },
        {
            "paperId": "rec222",
            "title": "Somewhat Relevant Paper",
            "year": 2023,
            "citationCount": 5,
            "isOpenAccess": False,
            "abstract": None,  # Edge case
            "authors": [],  # Edge case
        },
        {
            "paperId": "rec333",
            "title": "Extra Paper",
            "year": 2024,
            "citationCount": 1,
            "isOpenAccess": True,
            "authors": [{"name": "Junior Dev"}],
        },
    ]
}

BASE_URL_REGEX = r".*/recommendations/v1/papers/forpaper/.*"


@pytest.mark.unit
class TestAIRecommendationsFetcher:
    """Test Semantic Scholar Recommendations component logic."""

    # --- Validation ---

    @pytest.mark.asyncio
    async def test_recommendations_empty_id(self):
        """Tests validation when paper_id is empty."""
        component = AIRecommendationsComponent()
        component.paper_id = "   "
        component.max_results = 10
        results = await component.fetch_recommendations()
        assert "error" in results[0].data
        assert "Source Paper ID empty or could not be extracted" in results[0].data["error"]

    @pytest.mark.asyncio
    @respx.mock
    async def test_recommendations_smart_funnel_input(self):
        """Tests if the component correctly extracts paper_id from a Data list."""
        respx.get(url__regex=r".*/forpaper/smart_rec_777.*").respond(
            status_code=200, json={"recommendedPapers": [{"paperId": "mock_123", "title": "Mocked Paper"}]}
        )

        component = AIRecommendationsComponent()

        mock_data_list = [
            Data(data={"paper_id": "smart_rec_777", "title": "Seed Paper"}),
            Data(data={"paper_id": "other_paper_888"}),
        ]

        component.paper_data = mock_data_list
        component.max_results = 10

        results = await component.fetch_recommendations()

        assert "error" not in results[0].data, f"Internal Error: {results[0].data.get('error')}"
        assert len(respx.calls) == 1
        assert "smart_rec_777" in str(respx.calls.last.request.url)

    @pytest.mark.asyncio
    async def test_recommendations_empty_list_input(self):
        """Tests validation when input is an empty list."""
        component = AIRecommendationsComponent()
        component.paper_data = []
        component.max_results = 10

        results = await component.fetch_recommendations()

        assert "error" in results[0].data
        assert "Source Paper ID empty or could not be extracted" in results[0].data["error"]

    @pytest.mark.asyncio
    @respx.mock
    async def test_recommendations_id_stripping(self):
        """Tests if paper_id is stripped correctly before API call."""
        respx.get(url__regex=r".*/forpaper/clean_id_123.*").respond(status_code=200, json={"recommendedPapers": []})

        component = AIRecommendationsComponent()
        component.paper_id = "  clean_id_123  "
        await component.fetch_recommendations()
        assert len(respx.calls) == 1

    # --- Logic & Parsing ---

    @pytest.mark.asyncio
    @respx.mock
    async def test_recommendations_parsing_and_traceability(self):
        """Tests metadata extraction and source traceability mapping."""
        respx.get(url__regex=BASE_URL_REGEX).respond(status_code=200, json=MOCK_API_RESPONSE)

        component = AIRecommendationsComponent()
        component.paper_id = "source_123"
        component.max_results = 10

        results = await component.fetch_recommendations()

        assert len(results) == 3

        by_id = {r.data["recommended_paper_id"]: r.data for r in results}

        # Traceability check
        assert by_id["rec111"]["source_paper_id"] == "source_123"

        # Fallbacks check
        assert by_id["rec222"]["abstract"] == "No abstract available."
        assert by_id["rec222"]["authors"] == "Unknown"

    @pytest.mark.asyncio
    @respx.mock
    async def test_recommendations_max_results_slicing(self):
        """Tests if the output is strictly bounded by max_results."""
        respx.get(url__regex=BASE_URL_REGEX).respond(status_code=200, json=MOCK_API_RESPONSE)

        component = AIRecommendationsComponent()
        component.paper_id = "source_123"
        component.max_results = 2  # Lower than the 3 mocked items

        results = await component.fetch_recommendations()

        assert len(results) == 2
        # Ensures it kept the first two (AI relevance order)
        assert results[0].data["recommended_paper_id"] == "rec111"
        assert results[1].data["recommended_paper_id"] == "rec222"

    # --- Resilience ---

    @pytest.mark.asyncio
    @respx.mock
    async def test_recommendations_404_not_found(self):
        """Tests handling of invalid source paper ID."""
        respx.get(url__regex=BASE_URL_REGEX).respond(status_code=404)

        component = AIRecommendationsComponent()
        component.paper_id = "fake_id"

        results = await component.fetch_recommendations()
        assert "not found" in results[0].data["error"].lower()

    @pytest.mark.asyncio
    @respx.mock
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_recommendations_429_rate_limit(self, mock_sleep):
        """Tests HTTP 429 triggers the defense sleep and returns an error."""
        respx.get(url__regex=BASE_URL_REGEX).respond(status_code=429)

        component = AIRecommendationsComponent()
        component.paper_id = "source_123"

        results = await component.fetch_recommendations()

        assert "Rate limit" in results[0].data["error"]
        mock_sleep.assert_called_once_with(2)

    @pytest.mark.asyncio
    @respx.mock
    async def test_recommendations_http_error(self):
        """Tests handling of generic server errors."""
        respx.get(url__regex=BASE_URL_REGEX).respond(status_code=500, text="Internal Error")

        component = AIRecommendationsComponent()
        component.paper_id = "123"

        results = await component.fetch_recommendations()
        assert "HTTP Error 500" in results[0].data["error"]

    # --- DataFrame ---

    @pytest.mark.asyncio
    @respx.mock
    async def test_recommendations_dataframe_output(self):
        """Tests DataFrame conversion."""
        respx.get(url__regex=BASE_URL_REGEX).respond(status_code=200, json={"recommendedPapers": []})

        component = AIRecommendationsComponent()
        component.paper_id = "123"

        df = await component.fetch_recommendations_dataframe()
        assert isinstance(df, DataFrame)

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_recommendations_empty_results_as_error(self):
        """Tests that an empty recommendation list returns a Data object with an error key."""
        component = AIRecommendationsComponent()
        component.paper_id = "obscure-id"

        # Mock API returning empty list
        respx.get(url__regex=BASE_URL_REGEX).respond(status_code=200, json={"recommendedPapers": []})

        results = await component.fetch_recommendations()

        assert len(results) == 1
        assert "error" in results[0].data
        assert "No AI recommendations found" in results[0].data["error"]
        assert "error" in component.status.data
