import pytest
from langflow.components.youtube import YouTubeChannelComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestYouTubeChannelComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return YouTubeChannelComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "channel_url": "https://www.youtube.com/c/ExampleChannel",
            "api_key": "YOUR_API_KEY",
            "include_statistics": True,
            "include_branding": True,
            "include_playlists": False,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "youtube_channel", "file_name": "YouTubeChannel"},
        ]

    async def test_get_channel_info(self, component_class, default_kwargs):
        # Arrange
        component = component_class(**default_kwargs)

        # Act
        result = await component.get_channel_info()

        # Assert
        assert result is not None
        assert isinstance(result, pd.DataFrame)
        assert "title" in result.columns
        assert "description" in result.columns
        assert "channel_id" in result.columns

    async def test_invalid_channel_url(self, component_class):
        # Arrange
        invalid_kwargs = {
            "channel_url": "invalid_url",
            "api_key": "YOUR_API_KEY",
            "include_statistics": True,
            "include_branding": True,
            "include_playlists": False,
        }
        component = component_class(**invalid_kwargs)

        # Act
        result = await component.get_channel_info()

        # Assert
        assert result is not None
        assert isinstance(result, pd.DataFrame)
        assert "error" in result.columns
        assert result["error"].iloc[0] == "Channel not found"

    async def test_channel_with_playlists(self, component_class):
        # Arrange
        kwargs_with_playlists = {
            "channel_url": "https://www.youtube.com/c/ExampleChannel",
            "api_key": "YOUR_API_KEY",
            "include_statistics": True,
            "include_branding": True,
            "include_playlists": True,
        }
        component = component_class(**kwargs_with_playlists)

        # Act
        result = await component.get_channel_info()

        # Assert
        assert result is not None
        assert isinstance(result, pd.DataFrame)
        assert "playlist_title" in result.columns
