import pytest

from langflow.components.assemblyai import AssemblyAIGetSubtitles
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestAssemblyAIGetSubtitles(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return AssemblyAIGetSubtitles

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_key": "test_api_key",
            "transcription_result": {"id": "test_transcript_id"},
            "subtitle_format": "srt",
            "chars_per_caption": 0,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "assemblyai", "file_name": "AssemblyAIGetSubtitles"},
        ]

    def test_get_subtitles_success(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        # Mocking the aai.Transcript.get_by_id and its methods would be done here
        result = component.get_subtitles()
        assert result is not None
        assert "subtitles" in result.data
        assert result.data["format"] == "srt"

    def test_get_subtitles_error(self, component_class):
        default_kwargs = {
            "api_key": "test_api_key",
            "transcription_result": {"error": "Transcription not found"},
            "subtitle_format": "srt",
            "chars_per_caption": 0,
        }
        component = component_class(**default_kwargs)
        result = component.get_subtitles()
        assert result.data["error"] == "Transcription not found"

    def test_get_subtitles_transcript_error(self, component_class, default_kwargs):
        # Here we would simulate an error when fetching the transcript
        component = component_class(**default_kwargs)
        # Mocking the aai.Transcript.get_by_id to raise an exception would be done here
        result = component.get_subtitles()
        assert "error" in result.data
        assert "Getting transcription failed" in component.status
