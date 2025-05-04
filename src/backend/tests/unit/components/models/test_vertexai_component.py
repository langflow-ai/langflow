import pytest
from langflow.components.models import ChatVertexAIComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestChatVertexAIComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return ChatVertexAIComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "model_name": "gemini-1.5-pro",
            "project": "test-project",
            "location": "us-central1",
            "max_output_tokens": 100,
            "max_retries": 1,
            "temperature": 0.0,
            "top_k": 50,
            "top_p": 0.95,
            "verbose": False,
            "credentials": None,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "vertex_ai", "file_name": "ChatVertexAI"},
        ]

    async def test_build_model_with_credentials(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.credentials = "path/to/credentials.json"  # Mock path to credentials
        model = component.build_model()
        assert model is not None
        assert component.model_name == "gemini-1.5-pro"

    async def test_build_model_without_credentials(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.credentials = None
        model = component.build_model()
        assert model is not None
        assert component.model_name == "gemini-1.5-pro"

    async def test_invalid_credentials(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.credentials = "invalid/path/to/credentials.json"
        with pytest.raises(ImportError, match="Please install the langchain-google-vertexai package"):
            component.build_model()
