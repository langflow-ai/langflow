import pytest
from langflow.components.assemblyai import AssemblyAITranscriptionJobPoller
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestAssemblyAITranscriptionJobPoller(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return AssemblyAITranscriptionJobPoller

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_key": "test_api_key",
            "transcript_id": {"transcript_id": "test_transcript_id"},
            "polling_interval": 3.0,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "assemblyai", "file_name": "AssemblyAITranscriptionJobPoller"},
        ]

    async def test_poll_transcription_job_success(self, component_class, default_kwargs):
        component = await self.component_setup(component_class, default_kwargs)
        result = await component.poll_transcription_job()
        assert result is not None
        assert "text" in result.data
        assert "utterances" in result.data
        assert "id" in result.data

    async def test_poll_transcription_job_error(self, component_class, default_kwargs):
        default_kwargs["transcript_id"] = {"error": "Invalid transcript ID"}
        component = await self.component_setup(component_class, default_kwargs)
        result = await component.poll_transcription_job()
        assert result.data["error"] == "Invalid transcript ID"

    async def test_poll_transcription_job_exception(self, component_class, default_kwargs):
        # Simulate an exception during the polling
        default_kwargs["transcript_id"] = {"transcript_id": "non_existent_id"}
        component = await self.component_setup(component_class, default_kwargs)
        result = await component.poll_transcription_job()
        assert "error" in result.data
        assert "Getting transcription failed:" in result.data["error"]
