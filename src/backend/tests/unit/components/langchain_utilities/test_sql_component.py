import pytest

from langflow.components.langchain_utilities import SQLAgentComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestSQLAgentComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return SQLAgentComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"llm": "mock_llm", "database_uri": "sqlite:///test.db", "extra_tools": [], "_session_id": "123"}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "agents", "file_name": "SQLAgent"},
            {"version": "1.1.0", "module": "agents", "file_name": "sql_agent"},
        ]

    async def test_build_agent(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        agent_executor = component.build_agent()
        assert agent_executor is not None
        assert isinstance(agent_executor, AgentExecutor)

    async def test_agent_executor_configuration(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        agent_executor = component.build_agent()
        assert agent_executor.max_iterations == 5  # Assuming default max_iterations is 5
