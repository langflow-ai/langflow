from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("lfx_bundles")

from lfx_bundles.livetennisapi.player_search import LiveTennisPlayerSearchComponent

from tests.base import ComponentTestBaseWithoutClient


class TestLiveTennisPlayerSearchComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return LiveTennisPlayerSearchComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_key": "test-key",
            "search": "alcaraz",
            "limit": 50,
        }

    @pytest.fixture
    def file_names_mapping(self):
        # New component, no version history yet.
        return []

    @pytest.fixture(autouse=True)
    def mock_httpx_client(self):
        """Keep every test offline, including the inherited test_latest_version."""
        with patch("lfx_bundles.livetennisapi.player_search.httpx.Client") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {"data": [], "meta": {"count": 0}}
            mock_client.return_value.__enter__.return_value.get.return_value = mock_response
            yield mock_client

    def test_frontend_node(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)

        frontend_node = component.to_frontend_node()

        node_data = frontend_node["data"]["node"]
        assert node_data["display_name"] == "Player Search"
        assert node_data["icon"] == "LiveTennisAPI"
        assert node_data["template"]["search"]["value"] == "alcaraz"

    def test_fetch_players_success(self, component_class, default_kwargs, mock_httpx_client):
        component = component_class(**default_kwargs)
        mock_get = mock_httpx_client.return_value.__enter__.return_value.get
        mock_get.return_value.json.return_value = {
            "data": [
                {
                    "id": 7,
                    "name": "Carlos Alcaraz",
                    "tour": "atp",
                    "country": "esp",
                    "ranking": 1,
                    "ranking_points": 9000,
                    "ranking_movement": "same",
                    "hand": "R",
                    "birthday": "2003-05-05",
                    "is_doubles_team": False,
                }
            ],
            "meta": {"count": 1},
        }

        results = component.fetch_players()

        assert len(results) == 1
        row = results[0].data
        assert row["name"] == "Carlos Alcaraz"
        assert row["ranking"] == 1
        assert row["is_doubles_team"] is False

        _, kwargs = mock_get.call_args
        assert kwargs["params"]["search"] == "alcaraz"

    def test_empty_search_omits_param(self, component_class, default_kwargs, mock_httpx_client):
        component = component_class(**{**default_kwargs, "search": ""})

        component.fetch_players()

        _, kwargs = mock_httpx_client.return_value.__enter__.return_value.get.call_args
        assert "search" not in kwargs["params"]
