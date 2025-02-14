import pytest

from langflow.components.models import AzureChatOpenAIComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestAzureChatOpenAIComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return AzureChatOpenAIComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "azure_endpoint": "https://example-resource.azure.openai.com/",
            "azure_deployment": "my-deployment",
            "api_key": "my-secret-api-key",
            "api_version": "2024-10-01-preview",
            "temperature": 0.7,
            "max_tokens": 100,
            "_session_id": "123",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "azure_openai", "file_name": "AzureChatOpenAI"},
            {"version": "1.1.0", "module": "azure_openai", "file_name": "azure_chat_openai"},
        ]

    async def test_build_model(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        model = component.build_model()
        assert model is not None
        assert hasattr(model, "azure_endpoint")
        assert model.azure_endpoint == default_kwargs["azure_endpoint"]

    async def test_invalid_api_key(self, component_class):
        component = component_class(
            azure_endpoint="https://example-resource.azure.openai.com/",
            azure_deployment="my-deployment",
            api_key="invalid-key",
            api_version="2024-10-01-preview",
            temperature=0.7,
            max_tokens=100,
        )
        with pytest.raises(ValueError, match="Could not connect to AzureOpenAI API"):
            component.build_model()

    async def test_latest_version(self, component_class, default_kwargs):
        component_instance = await self.component_setup(component_class, default_kwargs)
        result = await component_instance.run()
        assert result is not None, "Component returned None for the latest version."
