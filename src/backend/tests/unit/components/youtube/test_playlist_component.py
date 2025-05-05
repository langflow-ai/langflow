import pytest
from langflow.components.youtube import YouTubePlaylistComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestYouTubePlaylistComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return YouTubePlaylistComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"playlist_url": "https://www.youtube.com/playlist?list=PL1234567890"}

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_extract_video_urls(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.extract_video_urls()
        assert result is not None
        assert isinstance(result, DataFrame)
        assert "video_url" in result.columns
        assert len(result) > 0  # Assuming the playlist has videos

    async def test_latest_version(self, component_class, default_kwargs):
        component_instance = await self.component_setup(component_class, default_kwargs)
        result = await component_instance.run()
        assert result is not None, "Component returned None for the latest version."
