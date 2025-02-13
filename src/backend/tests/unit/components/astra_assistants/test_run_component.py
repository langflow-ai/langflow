import pytest
from langflow.components.astra_assistants import AssistantsRun
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestAssistantsRunComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return AssistantsRun

    @pytest.fixture
    def default_kwargs(self):
        return {"assistant_id": "assistant_123", "user_message": "Hello, how can I help you?", "_session_id": "456"}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "assistants", "file_name": "AssistantsRun"},
            {"version": "1.1.0", "module": "assistants", "file_name": "assistants_run"},
        ]

    async def test_process_inputs_creates_thread(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.process_inputs()
        assert result is not None
        assert isinstance(result, Message)
        assert result.text != ""

    async def test_update_build_config_creates_thread_if_none(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {}
        component.update_build_config(build_config, None, "thread_id")
        assert "thread_id" in build_config
        assert component.thread_id is not None

    async def test_update_build_config_sets_thread_id(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {}
        component.update_build_config(build_config, "thread_789", "thread_id")
        assert build_config["thread_id"] == "thread_789"
        assert component.thread_id == "thread_789"
