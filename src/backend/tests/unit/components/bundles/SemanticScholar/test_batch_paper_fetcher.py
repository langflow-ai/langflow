"""Unit tests for Semantic Scholar Batch Paper Fetcher component."""

import pytest
import respx
from lfx.components.semanticscholar.batch_paper_fetcher import BatchPaperFetcherComponent
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame

MOCK_API_RESPONSE = [
    {
        "paperId": "p111",
        "title": "Batch Paper 1",
        "abstract": "A valid abstract.",
        "year": 2021,
        "citationCount": 10,
        "isOpenAccess": True,
        "url": "https://example.com/p111",
        "authors": [{"name": "John Doe"}],
    },
    {
        "paperId": "p222",
        "title": "Batch Paper 2",
        "abstract": None,  # Edge case: explicit null from API
        "year": 2022,
        "citationCount": 0,
        "isOpenAccess": False,
        "url": None,
        "authors": [],  # Edge case: empty authors
    },
    None,  # Edge case: The API could not find one of the requested IDs
]

BASE_URL = "https://api.semanticscholar.org/graph/v1/paper/batch"


@pytest.mark.unit
class TestBatchPaperFetcher:
    """Test Semantic Scholar Batch Paper Fetcher logic."""

    # --- Validation and Edge Cases ---

    @pytest.mark.asyncio
    async def test_batch_fetcher_empty_input(self):
        """Tests validation when input is entirely missing."""
        component = BatchPaperFetcherComponent()
        component.paper_ids = None
        results = await component.fetch_batch()
        assert "error" in results[0].data

    @pytest.mark.asyncio
    async def test_batch_fetcher_invalid_string(self):
        """Tests validation when string contains only commas and spaces."""
        component = BatchPaperFetcherComponent()
        component.paper_ids = " , ,,   "
        results = await component.fetch_batch()
        assert "error" in results[0].data
        assert "No valid Paper IDs" in results[0].data["error"]

    # --- The Smart Funnel (Input Parsing) ---

    @pytest.mark.asyncio
    @respx.mock
    async def test_batch_fetcher_string_input(self):
        """Tests parsing of a standard comma-separated string."""
        route = respx.post(BASE_URL).respond(status_code=200, json=[MOCK_API_RESPONSE[0]])

        component = BatchPaperFetcherComponent()
        # Includes spaces to test stripping
        component.paper_ids = "p111,  p222 ,p333"
        await component.fetch_batch()

        # Verify if the POST payload was correctly structured
        request = route.calls.last.request
        payload = request.read().decode("utf-8")
        assert "p111" in payload
        assert "p222" in payload
        assert "p333" in payload

    @pytest.mark.asyncio
    @respx.mock
    async def test_batch_fetcher_data_list_input(self):
        """Tests parsing when receiving a list of Data objects from other components."""
        route = respx.post(BASE_URL).respond(status_code=200, json=[MOCK_API_RESPONSE[0]])

        mock_data_input = [
            Data(data={"citing_paper_id": "cite_123"}),
            Data(data={"recommended_paper_id": "rec_456"}),
            Data(data={"paper_id": "norm_789"}),
            Data(data={"referenced_paper_id": "ref_101"}),
            Data(data={"unrelated_key": "ignore_me"}),  # Should be ignored
        ]

        component = BatchPaperFetcherComponent()
        component.paper_data = mock_data_input
        await component.fetch_batch()

        request = route.calls.last.request
        payload = request.read().decode("utf-8")
        assert "cite_123" in payload
        assert "rec_456" in payload
        assert "norm_789" in payload
        assert "ref_101" in payload
        assert "ignore_me" not in payload

    @pytest.mark.asyncio
    async def test_batch_fetcher_empty_list_input(self):
        """Tests validation when input is an empty list."""
        component = BatchPaperFetcherComponent()
        component.paper_data = []
        results = await component.fetch_batch()
        assert "error" in results[0].data
        assert "No valid Paper IDs could be extracted from either input" in results[0].data["error"]

    @pytest.mark.asyncio
    @respx.mock
    async def test_batch_fetcher_500_limit_truncation(self):
        """Tests if the component strictly enforces the 500 ID API limit."""
        route = respx.post(BASE_URL).respond(status_code=200, json=[])

        # Generate 600 unique IDs
        massive_input = ",".join([f"id_{i}" for i in range(600)])

        component = BatchPaperFetcherComponent()
        component.paper_ids = massive_input
        await component.fetch_batch()

        import json

        request = route.calls.last.request
        payload = json.loads(request.read().decode("utf-8"))

        # Must cap exactly at 500
        assert len(payload["ids"]) == 500

    # --- Parsing & Fallbacks ---

    @pytest.mark.asyncio
    @respx.mock
    async def test_batch_fetcher_parsing_and_fallbacks(self):
        """Tests correct mapping and handling of missing/null fields."""
        respx.post(BASE_URL).respond(status_code=200, json=MOCK_API_RESPONSE)

        component = BatchPaperFetcherComponent()
        component.paper_ids = "p111,p222,invalid_one"

        results = await component.fetch_batch()

        # The 'None' entry in MOCK_API_RESPONSE should be safely skipped
        assert len(results) == 2

        by_id = {r.data["paper_id"]: r.data for r in results}

        # Check regular mappings
        assert by_id["p111"]["authors"] == "John Doe"
        assert by_id["p111"]["citation_count"] == 10

        # Check explicit fallbacks
        assert by_id["p222"]["abstract"] == "No abstract available."
        assert by_id["p222"]["authors"] == "Unknown"

    # --- Network Resilience ---

    @pytest.mark.asyncio
    @respx.mock
    async def test_batch_fetcher_429_rate_limit(self):
        """Tests if 429 returns a direct error (batch requests don't use sleep)."""
        respx.post(BASE_URL).respond(status_code=429)

        component = BatchPaperFetcherComponent()
        component.paper_ids = "p111"

        results = await component.fetch_batch()

        assert "Rate limit" in results[0].data["error"]

    @pytest.mark.asyncio
    @respx.mock
    async def test_batch_fetcher_http_error(self):
        """Tests generic 500 server error handling."""
        respx.post(BASE_URL).respond(status_code=500, text="Server Overload")

        component = BatchPaperFetcherComponent()
        component.paper_ids = "p111"

        results = await component.fetch_batch()
        assert "HTTP Error 500" in results[0].data["error"]

    # --- DataFrame Output ---

    @pytest.mark.asyncio
    @respx.mock
    async def test_batch_fetcher_dataframe_output(self):
        """Tests DataFrame conversion."""
        respx.post(BASE_URL).respond(status_code=200, json=[MOCK_API_RESPONSE[0]])

        component = BatchPaperFetcherComponent()
        component.paper_ids = "p111"

        df = await component.fetch_batch_dataframe()
        assert isinstance(df, DataFrame)
