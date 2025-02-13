import pytest

from langflow.components.langchain_utilities import CSVAgentComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestCSVAgentComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return CSVAgentComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "llm": "mock_llm",
            "path": "mock_path.csv",
            "agent_type": "openai-tools",
            "input_value": "mock input",
            "pandas_kwargs": {},
            "_session_id": "123",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "agents", "file_name": "CSVAgent"},
            {"version": "1.1.0", "module": "agents", "file_name": "csv_agent"},
        ]

    async def test_build_agent_response(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        response = await component.build_agent_response()
        assert response is not None
        assert isinstance(response, Message)
        assert "output" in response.text

    async def test_build_agent(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        agent = await component.build_agent()
        assert agent is not None
        assert isinstance(agent, AgentExecutor)
        assert component.status.text == str(agent)
