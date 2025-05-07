import pytest
from langflow.components.astra_assistants import AssistantsCreateAssistant
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestAssistantsCreateAssistant(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return AssistantsCreateAssistant

    @pytest.fixture
    def default_kwargs(self):
        return {
            "assistant_name": "Test Assistant",
            "instructions": "This is a test assistant.",
            "model": "test-model",
            "env_set": "dummy_env_set",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "assistants", "file_name": "AssistantsCreateAssistant"},
        ]

    async def test_process_inputs(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.process_inputs()
        assert result is not None
        assert hasattr(result, "text")
        assert result.text == "expected_assistant_id"  # Replace with actual expected ID if known

    async def test_latest_version(self, component_class, default_kwargs):
        component_instance = await self.component_setup(component_class, default_kwargs)
        result = await component_instance.run()
        assert result is not None, "Component returned None for the latest version."
