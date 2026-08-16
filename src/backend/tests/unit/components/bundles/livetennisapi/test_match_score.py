from unittest.mock import MagicMock, patch

import httpx
import pytest

pytest.importorskip("lfx_bundles")

from lfx_bundles.livetennisapi.match_score import LiveTennisMatchScoreComponent

from tests.base import ComponentTestBaseWithoutClient


class TestLiveTennisMatchScoreComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return LiveTennisMatchScoreComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_key": "test-key",
            "match_id": "123",
        }

    @pytest.fixture
    def file_names_mapping(self):
        # New component, no version history yet.
        return []

    @pytest.fixture(autouse=True)
    def mock_httpx_client(self):
        """Keep every test offline, including the inherited test_latest_version."""
        with patch("lfx_bundles.livetennisapi.match_score.httpx.Client") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {}
            mock_client.return_value.__enter__.return_value.get.return_value = mock_response
            yield mock_client

    def test_frontend_node(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)

        frontend_node = component.to_frontend_node()

        node_data = frontend_node["data"]["node"]
        assert node_data["display_name"] == "Match Score"
        assert node_data["icon"] == "LiveTennisAPI"
        assert node_data["template"]["match_id"]["value"] == "123"

    def test_fetch_score_success(self, component_class, default_kwargs, mock_httpx_client):
        component = component_class(**default_kwargs)
        mock_get = mock_httpx_client.return_value.__enter__.return_value.get
        mock_get.return_value.json.return_value = {
            "sets": [1, 0],
            "games": [[6, 3], [2, 1]],
            "points": ["40", "30"],
            "server": 2,
            "is_tiebreak": False,
            "timestamp": "2026-08-16T12:00:00Z",
        }

        result = component.fetch_score()

        assert result.data["sets"] == [1, 0]
        assert result.data["server"] == 2
        assert "sets 1-0" in result.text
        assert "games 6-2 3-1" in result.text

        args, kwargs = mock_get.call_args
        assert args[0].endswith("/matches/123/score")
        assert kwargs["headers"]["X-API-Key"] == "test-key"

    def test_non_integer_match_id_returns_error(self, component_class, default_kwargs):
        component = component_class(**{**default_kwargs, "match_id": "not-a-number"})

        result = component.fetch_score()

        assert "error" in result.data

    def test_not_found_returns_friendly_error(self, component_class, default_kwargs, mock_httpx_client):
        component = component_class(**default_kwargs)
        mock_response = mock_httpx_client.return_value.__enter__.return_value.get.return_value
        mock_response.status_code = 404
        mock_response.text = '{"error":"not_found"}'
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=mock_response
        )

        result = component.fetch_score()

        assert "error" in result.data
        assert "not found" in result.text

    def test_malformed_payload_returns_error_data(self, component_class, default_kwargs, mock_httpx_client):
        """A 200 response whose body is not a score object yields an error Data result."""
        component = component_class(**default_kwargs)
        mock_httpx_client.return_value.__enter__.return_value.get.return_value.json.return_value = [1, 2, 3]

        result = component.fetch_score()

        assert "error" in result.data
