import pytest
from langflow.components.assemblyai import AssemblyAILeMUR
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestAssemblyAILeMURComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return AssemblyAILeMUR

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_key": "test_api_key",
            "transcription_result": {"id": "transcript_id"},
            "prompt": "What is the summary?",
            "final_model": "claude3_5_sonnet",
            "temperature": 0.5,
            "max_output_size": 1000,
            "endpoint": "summary",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "assemblyai", "file_name": "AssemblyAILeMUR"},
        ]

    async def test_run_lemur_with_valid_input(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.run_lemur()
        assert result is not None
        assert "data" in result
        assert "error" not in result.data

    async def test_run_lemur_without_transcription_result(self, component_class):
        component = component_class(api_key="test_api_key", prompt="What is the summary?", endpoint="summary")
        result = await component.run_lemur()
        assert result is not None
        assert "error" in result.data
        assert result.data["error"] == "Either a Transcription Result or valid Transcript IDs must be provided"

    async def test_run_lemur_without_prompt_for_task(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.prompt = ""  # No prompt specified
        result = await component.run_lemur()
        assert result is not None
        assert "error" in result.data
        assert result.data["error"] == "No prompt specified for the task endpoint"

    async def test_run_lemur_without_questions_for_question_answer(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.endpoint = "question-answer"  # Set endpoint to question-answer
        component.questions = ""  # No questions specified
        result = await component.run_lemur()
        assert result is not None
        assert "error" in result.data
        assert result.data["error"] == "No Questions were provided for the question-answer endpoint"

    async def test_run_lemur_with_invalid_endpoint(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.endpoint = "invalid_endpoint"  # Invalid endpoint
        result = await component.run_lemur()
        assert result is not None
        assert "error" in result.data
        assert result.data["error"] == "Endpoint not supported: invalid_endpoint"
