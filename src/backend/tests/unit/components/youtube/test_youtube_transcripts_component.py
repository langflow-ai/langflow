import pytest

from langflow.components.youtube import YouTubeTranscriptsComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestYouTubeTranscriptsComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return YouTubeTranscriptsComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "chunk_size_seconds": 60,
            "translation": "",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "youtube_transcripts", "file_name": "YouTubeTranscripts"},
        ]

    async def test_get_dataframe_output(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.get_dataframe_output()
        assert result is not None
        assert isinstance(result, pd.DataFrame)
        assert "timestamp" in result.data.columns
        assert "text" in result.data.columns

    async def test_get_message_output(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.get_message_output()
        assert result is not None
        assert isinstance(result, Message)
        assert isinstance(result.text, str)

    async def test_invalid_url(self, component_class):
        component = component_class(url="invalid_url", chunk_size_seconds=60, translation="")
        dataframe_result = await component.get_dataframe_output()
        message_result = await component.get_message_output()

        assert "error" in dataframe_result.data.columns
        assert "Failed to get YouTube transcripts" in dataframe_result.data["error"].values[0]
        assert "Failed to get YouTube transcripts" in message_result.text
