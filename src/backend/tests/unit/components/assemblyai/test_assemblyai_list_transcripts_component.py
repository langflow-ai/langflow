import pytest
from langflow.components.assemblyai import AssemblyAIListTranscripts
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestAssemblyAIListTranscripts(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return AssemblyAIListTranscripts

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_key": "test_api_key",
            "limit": 20,
            "status_filter": "all",
            "created_on": None,
            "throttled_only": False,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "assemblyai", "file_name": "AssemblyAIListTranscripts"},
        ]

    async def test_list_transcripts(self, component_class, default_kwargs):
        component = await self.component_setup(component_class, default_kwargs)
        result = await component.list_transcripts()
        assert isinstance(result, list), "Expected result to be a list."
        # Additional assertions can be added based on expected output structure

    async def test_list_transcripts_with_limit(self, component_class, default_kwargs):
        component = await self.component_setup(component_class, {**default_kwargs, "limit": 5})
        result = await component.list_transcripts()
        assert len(result) <= 5, "Expected result length to be less than or equal to limit."

    async def test_list_transcripts_with_status_filter(self, component_class, default_kwargs):
        component = await self.component_setup(component_class, {**default_kwargs, "status_filter": "completed"})
        result = await component.list_transcripts()
        # Assuming the result contains a status field to check against
        assert all(transcript.status == "completed" for transcript in result), (
            "All transcripts should have status 'completed'."
        )

    async def test_list_transcripts_error_handling(self, component_class, default_kwargs):
        component = await self.component_setup(component_class, {**default_kwargs, "api_key": "invalid_key"})
        result = await component.list_transcripts()
        assert len(result) == 1 and "error" in result[0].data, "Expected an error message in the result."
