from unittest.mock import MagicMock, patch

import httpx
import pytest

pytest.importorskip("lfx_bundles")

from lfx_bundles.livetennisapi.live_matches import LiveTennisMatchesComponent

from tests.base import ComponentTestBaseWithoutClient


class TestLiveTennisMatchesComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return LiveTennisMatchesComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_key": "test-key",
            "match_status": "live",
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
        with patch("lfx_bundles.livetennisapi.live_matches.httpx.Client") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {"data": [], "meta": {"count": 0}}
            mock_client.return_value.__enter__.return_value.get.return_value = mock_response
            yield mock_client

    def test_frontend_node(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)

        frontend_node = component.to_frontend_node()

        node_data = frontend_node["data"]["node"]
        assert node_data["display_name"] == "Live Matches"
        assert node_data["icon"] == "LiveTennisAPI"
        assert "api_key" in node_data["template"]
        assert node_data["template"]["api_key"]["password"] is True
        assert node_data["template"]["match_status"]["options"] == ["live", "upcoming"]

    def test_fetch_matches_success(self, component_class, default_kwargs, mock_httpx_client):
        component = component_class(**default_kwargs)
        mock_get = mock_httpx_client.return_value.__enter__.return_value.get
        mock_get.return_value.json.return_value = {
            "data": [
                {
                    "id": 123,
                    "status": "live",
                    "tour": "atp",
                    "tournament": "Cincinnati Open",
                    "round": "Quarterfinal",
                    "surface": "hard",
                    "players": {
                        "p1": {"id": 1, "name": "Player One", "country": "sui", "ranking": 3},
                        "p2": {"id": 2, "name": "Player Two", "country": "esp", "ranking": 1},
                    },
                    "score": {
                        "sets": [1, 0],
                        "games": [[6, 3], [4, 2]],
                        "points": ["30", "15"],
                        "server": 1,
                    },
                }
            ],
            "meta": {"count": 1},
        }

        results = component.fetch_matches()

        assert len(results) == 1
        row = results[0].data
        assert row["id"] == 123
        assert row["player1"] == "Player One"
        assert row["player2"] == "Player Two"
        assert row["sets"] == "1-0"
        assert row["games"] == "6-4 3-2"
        assert row["points"] == "30-15"

        _, kwargs = mock_get.call_args
        assert kwargs["params"]["status"] == "live"
        assert "tour" not in kwargs["params"]
        assert kwargs["headers"]["X-API-Key"] == "test-key"

    def test_tour_filter_is_sent(self, component_class, default_kwargs, mock_httpx_client):
        component = component_class(**{**default_kwargs, "tour": "wta"})

        component.fetch_matches()

        _, kwargs = mock_httpx_client.return_value.__enter__.return_value.get.call_args
        assert kwargs["params"]["tour"] == "wta"

    def test_http_error_returns_error_data(self, component_class, default_kwargs, mock_httpx_client):
        component = component_class(**default_kwargs)
        mock_response = mock_httpx_client.return_value.__enter__.return_value.get.return_value
        mock_response.status_code = 401
        mock_response.text = '{"error":"unauthorized"}'
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401", request=MagicMock(), response=mock_response
        )

        results = component.fetch_matches()

        assert len(results) == 1
        assert "error" in results[0].data

    def test_malformed_payload_returns_error_data(self, component_class, default_kwargs, mock_httpx_client):
        """A 200 response whose body is not the documented shape yields an error Data row."""
        component = component_class(**default_kwargs)
        mock_httpx_client.return_value.__enter__.return_value.get.return_value.json.return_value = {"data": "nope"}

        results = component.fetch_matches()

        assert len(results) == 1
        assert "error" in results[0].data

    def test_limit_is_clamped_to_api_range(self, component_class, default_kwargs, mock_httpx_client):
        """Out-of-range limit values are clamped to the API's 1-200 range."""
        component = component_class(**{**default_kwargs, "limit": -5})

        component.fetch_matches()

        _, kwargs = mock_httpx_client.return_value.__enter__.return_value.get.call_args
        assert kwargs["params"]["limit"] == 1
