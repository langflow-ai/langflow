import pytest
from langflow.components.assemblyai import AssemblyAITranscriptionJobCreator
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestAssemblyAITranscriptionJobCreator(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return AssemblyAITranscriptionJobCreator

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_key": "test_api_key",
            "audio_file": "test_audio_file.wav",
            "audio_file_url": None,
            "speech_model": "best",
            "language_detection": True,
            "language_code": None,
            "speaker_labels": False,
            "speakers_expected": None,
            "punctuate": True,
            "format_text": True,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "transcription", "file_name": "AssemblyAITranscriptionJobCreator"},
        ]

    def test_create_transcription_job_success(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.create_transcription_job()
        assert result is not None
        assert "transcript_id" in result.data

    def test_create_transcription_job_audio_file_not_found(self, component_class, default_kwargs):
        default_kwargs["audio_file"] = "non_existent_file.wav"
        component = component_class(**default_kwargs)
        result = component.create_transcription_job()
        assert result.data["error"] == "Error: Audio file not found"

    def test_create_transcription_job_no_audio_specified(self, component_class, default_kwargs):
        default_kwargs["audio_file"] = None
        component = component_class(**default_kwargs)
        result = component.create_transcription_job()
        assert result.data["error"] == "Error: Either an audio file or an audio URL must be specified"

    def test_create_transcription_job_invalid_speakers_expected(self, component_class, default_kwargs):
        default_kwargs["speakers_expected"] = "invalid_number"
        component = component_class(**default_kwargs)
        result = component.create_transcription_job()
        assert result.data["error"] == "Error: Expected Number of Speakers must be a valid integer"
