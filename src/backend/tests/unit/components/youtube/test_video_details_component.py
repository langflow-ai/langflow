import pytest
from langflow.components.youtube import YouTubeVideoDetailsComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestYouTubeVideoDetailsComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return YouTubeVideoDetailsComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "api_key": "YOUR_API_KEY",
            "include_statistics": True,
            "include_content_details": True,
            "include_tags": True,
            "include_thumbnails": True,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "youtube_video_details", "file_name": "YouTubeVideoDetails"},
        ]

    async def test_get_video_details(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.get_video_details()
        assert result is not None
        assert "video_id" in result.columns
        assert "title" in result.columns
        assert "view_count" in result.columns
        assert "like_count" in result.columns

    async def test_video_not_found(self, component_class):
        component = component_class(video_url="https://www.youtube.com/watch?v=INVALID_ID", api_key="YOUR_API_KEY")
        result = await component.get_video_details()
        assert result is not None
        assert "error" in result.columns
        assert result["error"].iloc[0] == "Video not found."

    async def test_api_forbidden(self, component_class):
        component = component_class(video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ", api_key="INVALID_API_KEY")
        result = await component.get_video_details()
        assert result is not None
        assert "error" in result.columns
        assert result["error"].iloc[0] == "API quota exceeded or access forbidden."
