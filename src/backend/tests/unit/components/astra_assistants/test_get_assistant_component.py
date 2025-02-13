import pytest
from langflow.components.astra_assistants import AssistantsGetAssistantName
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestAssistantsGetAssistantName(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return AssistantsGetAssistantName

    @pytest.fixture
    def default_kwargs(self):
        return {"assistant_id": "12345", "env_set": "dummy_env"}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "assistants", "file_name": "AssistantsGetAssistantName"},
        ]

    async def test_process_inputs(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.process_inputs()
        assert result is not None
        assert isinstance(result, Message)
        assert hasattr(result, "text")

    async def test_latest_version(self, component_class, default_kwargs):
        component_instance = await self.component_setup(component_class, default_kwargs)
        result = await component_instance.run()
        assert result is not None, "Component returned None for the latest version."
