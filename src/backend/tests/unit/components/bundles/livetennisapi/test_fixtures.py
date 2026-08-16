from unittest.mock import MagicMock, patch

import httpx
import pytest

pytest.importorskip("lfx_bundles")

from lfx_bundles.livetennisapi.fixtures import LiveTennisFixturesComponent

from tests.base import ComponentTestBaseWithoutClient


class TestLiveTennisFixturesComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return LiveTennisFixturesComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_key": "test-key",
            "tour": "all",
            "limit": 50,
        }

    @pytest.fixture
    def file_names_mapping(self):
        # New component, no version history yet.
        return []

    @pytest.fixture(autouse=True)
    def mock_httpx_client(self):
        """Keep every test offline, including the inherited test_latest_version."""
        with patch("lfx_bundles.livetennisapi.fixtures.httpx.Client") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {"data": [], "meta": {"count": 0}}
            mock_client.return_value.__enter__.return_value.get.return_value = mock_response
            yield mock_client

    def test_frontend_node(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)

        frontend_node = component.to_frontend_node()

        node_data = frontend_node["data"]["node"]
        assert node_data["display_name"] == "Fixtures"
        assert node_data["icon"] == "LiveTennisAPI"
        assert node_data["template"]["api_key"]["password"] is True

    def test_fetch_fixtures_success(self, component_class, default_kwargs, mock_httpx_client):
        component = component_class(**default_kwargs)
        mock_get = mock_httpx_client.return_value.__enter__.return_value.get
        mock_get.return_value.json.return_value = {
            "data": [
                {
                    "id": 456,
                    "event_date": "2026-08-17",
                    "start_time": "2026-08-17T11:00:00Z",
                    "tournament": "US Open",
                    "round": "1st Round",
                    "round_code": "R128",
                    "tour": "atp",
                    "surface": "hard",
                    "player1_name": "Player One",
                    "player1_id": 1,
                    "player2_name": "Player Two",
                    "player2_id": None,
                    "status": "upcoming",
                }
            ],
            "meta": {"count": 1},
        }

        results = component.fetch_fixtures()

        assert len(results) == 1
        row = results[0].data
        assert row["id"] == 456
        assert row["start_time"] == "2026-08-17T11:00:00Z"
        assert row["player2_id"] is None
        assert results[0].text == "Player One vs Player Two — US Open"

    def test_timeout_returns_error_data(self, component_class, default_kwargs, mock_httpx_client):
        component = component_class(**default_kwargs)
        mock_httpx_client.return_value.__enter__.return_value.get.side_effect = httpx.TimeoutException("timeout")

        results = component.fetch_fixtures()

        assert len(results) == 1
        assert "error" in results[0].data

    def test_http_error_returns_error_data(self, component_class, default_kwargs, mock_httpx_client):
        """An API error (e.g. 401) comes back as a single error Data row, not an exception."""
        component = component_class(**default_kwargs)
        mock_response = mock_httpx_client.return_value.__enter__.return_value.get.return_value
        mock_response.status_code = 401
        mock_response.text = '{"error":"unauthorized"}'
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401", request=MagicMock(), response=mock_response
        )

        results = component.fetch_fixtures()

        assert len(results) == 1
        assert "error" in results[0].data

    def test_malformed_payload_returns_error_data(self, component_class, default_kwargs, mock_httpx_client):
        """A 200 response whose body is not the documented shape yields an error Data row."""
        component = component_class(**default_kwargs)
        mock_httpx_client.return_value.__enter__.return_value.get.return_value.json.return_value = None

        results = component.fetch_fixtures()

        assert len(results) == 1
        assert "error" in results[0].data

    def test_limit_is_clamped_to_api_range(self, component_class, default_kwargs, mock_httpx_client):
        """Out-of-range limit values are clamped to the API's 1-200 range."""
        component = component_class(**{**default_kwargs, "limit": 0})

        component.fetch_fixtures()

        _, kwargs = mock_httpx_client.return_value.__enter__.return_value.get.call_args
        assert kwargs["params"]["limit"] == 1
