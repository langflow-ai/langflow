import pytest
from langflow.components.youtube import YouTubeCommentsComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestYouTubeCommentsComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return YouTubeCommentsComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "api_key": "YOUR_API_KEY",
            "max_results": 20,
            "sort_by": "relevance",
            "include_replies": False,
            "include_metrics": True,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "youtube_comments", "file_name": "YouTubeComments"},
        ]

    async def test_get_video_comments(self, component_class, default_kwargs):
        # Arrange
        component = await self.component_setup(component_class, default_kwargs)

        # Act
        result = await component.get_video_comments()

        # Assert
        assert isinstance(result, pd.DataFrame), "Result should be a DataFrame."
        assert not result.empty, "Result DataFrame should not be empty."
        assert "comment_id" in result.columns, "DataFrame should contain 'comment_id' column."
        assert "video_id" in result.columns, "DataFrame should contain 'video_id' column."

    async def test_invalid_video_url(self, component_class):
        # Arrange
        invalid_kwargs = {
            "video_url": "invalid_url",
            "api_key": "YOUR_API_KEY",
            "max_results": 20,
            "sort_by": "relevance",
            "include_replies": False,
            "include_metrics": True,
        }
        component = await self.component_setup(component_class, invalid_kwargs)

        # Act
        result = await component.get_video_comments()

        # Assert
        assert isinstance(result, pd.DataFrame), "Result should be a DataFrame."
        assert "error" in result.columns, "DataFrame should contain 'error' column."
        assert not result.empty, "Result DataFrame should not be empty."
        assert result["error"].iloc[0] == "Video not found.", "Error message should indicate video not found."

    async def test_comments_disabled(self, component_class):
        # Arrange
        disabled_comments_kwargs = {
            "video_url": "https://www.youtube.com/watch?v=VIDEO_WITH_DISABLED_COMMENTS",
            "api_key": "YOUR_API_KEY",
            "max_results": 20,
            "sort_by": "relevance",
            "include_replies": False,
            "include_metrics": True,
        }
        component = await self.component_setup(component_class, disabled_comments_kwargs)

        # Act
        result = await component.get_video_comments()

        # Assert
        assert isinstance(result, pd.DataFrame), "Result should be a DataFrame."
        assert "error" in result.columns, "DataFrame should contain 'error' column."
        assert not result.empty, "Result DataFrame should not be empty."
        assert result["error"].iloc[0] == "Comments are disabled for this video or API quota exceeded.", (
            "Error message should indicate comments are disabled."
        )
