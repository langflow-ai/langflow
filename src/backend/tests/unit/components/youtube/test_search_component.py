import pytest
from langflow.components.youtube import YouTubeSearchComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestYouTubeSearchComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return YouTubeSearchComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "query": "Python programming",
            "api_key": "fake_api_key",
            "max_results": 5,
            "order": "relevance",
            "include_metadata": True,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "youtube_search", "file_name": "YouTubeSearch"},
        ]

    async def test_search_videos(self, component_class, default_kwargs):
        # Arrange
        component = component_class(**default_kwargs)

        # Act
        result = await component.search_videos()

        # Assert
        assert isinstance(result, DataFrame)
        assert not result.empty, "Expected non-empty results for the search query."
        assert "video_id" in result.columns, "Expected 'video_id' in the results."
        assert "title" in result.columns, "Expected 'title' in the results."
        assert "description" in result.columns, "Expected 'description' in the results."

    async def test_search_videos_with_error(self, component_class):
        # Arrange
        component = component_class(query="Invalid query", api_key="invalid_key")

        # Act
        result = await component.search_videos()

        # Assert
        assert isinstance(result, DataFrame)
        assert "error" in result.columns, "Expected 'error' in the results when API key is invalid."
