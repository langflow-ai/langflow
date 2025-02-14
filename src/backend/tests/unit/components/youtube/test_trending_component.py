import pytest

from langflow.components.youtube import YouTubeTrendingComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestYouTubeTrendingComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return YouTubeTrendingComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_key": "YOUR_API_KEY",
            "region": "Global",
            "category": "All",
            "max_results": 10,
            "include_statistics": True,
            "include_content_details": True,
            "include_thumbnails": True,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "youtube_trending", "file_name": "YouTubeTrending"},
        ]

    async def test_get_trending_videos(self, component_class, default_kwargs):
        # Arrange
        component = component_class(**default_kwargs)

        # Act
        result = await component.get_trending_videos()

        # Assert
        assert isinstance(result, pd.DataFrame), "Result should be a DataFrame."
        assert not result.empty, "Result DataFrame should not be empty."

    async def test_invalid_max_results(self, component_class, default_kwargs):
        # Arrange
        default_kwargs["max_results"] = 100  # Exceeding max limit
        component = component_class(**default_kwargs)

        # Act
        result = await component.get_trending_videos()

        # Assert
        assert isinstance(result, pd.DataFrame), "Result should be a DataFrame."
        assert result.empty or result.shape[0] <= 50, "Result should not exceed 50 entries."

    async def test_api_key_required(self, component_class):
        # Arrange
        component = component_class(api_key="", region="Global", category="All", max_results=10)

        # Act
        result = await component.get_trending_videos()

        # Assert
        assert isinstance(result, pd.DataFrame), "Result should be a DataFrame."
        assert "error" in result.columns, "Result should contain an error column."
        assert not result.empty, "Error DataFrame should not be empty."
