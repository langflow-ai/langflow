import pytest
from langflow.components.agents import AgentComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestAgentComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return AgentComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "agent_llm": "OpenAI",
            "system_prompt": "You are a helpful assistant.",
            "add_current_date_tool": True,
            "_session_id": "123",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "langchain_utilities", "file_name": "Agent"},
            {"version": "1.1.0", "module": "langchain_utilities", "file_name": "agent"},
        ]

    async def test_message_response_with_valid_llm(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.message_response()
        assert result is not None
        assert isinstance(result, Message)

    async def test_message_response_without_llm(self, component_class):
        component = component_class(agent_llm=None)
        with pytest.raises(ValueError, match="No language model selected"):
            await component.message_response()

    async def test_message_response_without_tools(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.tools = []  # Simulate no tools available
        with pytest.raises(ValueError, match="Tools are required to run the agent."):
            await component.message_response()

    async def test_get_memory_data(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        memory_data = await component.get_memory_data()
        assert isinstance(memory_data, list)  # Assuming it returns a list of messages

    async def test_update_build_config(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = dotdict({"agent_llm": {"value": "OpenAI"}})
        updated_config = await component.update_build_config(build_config, "Custom", "agent_llm")
        assert updated_config["agent_llm"]["value"] == "Custom"
