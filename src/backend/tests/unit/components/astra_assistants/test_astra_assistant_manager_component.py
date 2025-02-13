import pytest

from langflow.components.astra_assistants import AstraAssistantManager
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestAstraAssistantManager(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return AstraAssistantManager

    @pytest.fixture
    def default_kwargs(self):
        return {
            "model_name": "gpt-4o-mini",
            "instructions": "Provide assistance based on user input.",
            "user_message": "Hello, how can you help me?",
            "input_tools": [],
            "file": None,
            "input_thread_id": None,
            "input_assistant_id": None,
            "env_set": None,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "astra_assistant_manager", "file_name": "AstraAssistantManager"},
        ]

    async def test_get_assistant_response(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        await component.initialize()
        response = await component.get_assistant_response()
        assert response is not None
        assert isinstance(response.text, str)

    async def test_get_tool_output(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        await component.initialize()
        tool_output = await component.get_tool_output()
        assert tool_output is not None
        assert isinstance(tool_output.text, str)

    async def test_get_thread_id(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        await component.initialize()
        thread_id = await component.get_thread_id()
        assert thread_id is not None
        assert isinstance(thread_id.text, str)

    async def test_get_assistant_id(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        await component.initialize()
        assistant_id = await component.get_assistant_id()
        assert assistant_id is not None
        assert isinstance(assistant_id.text, str)

    async def test_get_vs_id(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        await component.initialize()
        vs_id = await component.get_vs_id()
        assert vs_id is not None
        assert isinstance(vs_id.text, str)

    async def test_process_inputs(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        await component.process_inputs()
        assert component.input_tools == []
        assert component.instructions == "Provide assistance based on user input."
