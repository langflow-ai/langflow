import pytest
from langflow.components.langchain_utilities import VectorStoreRouterAgentComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestVectorStoreRouterAgentComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return VectorStoreRouterAgentComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"llm": "mock_llm", "vectorstores": ["mock_vectorstore1", "mock_vectorstore2"], "_session_id": "123"}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "agents", "file_name": "VectorStoreRouterAgent"},
        ]

    async def test_build_agent(self, component_class, default_kwargs):
        # Arrange
        component = component_class(**default_kwargs)

        # Act
        agent = component.build_agent()

        # Assert
        assert agent is not None
        assert hasattr(agent, "llm")
        assert hasattr(agent, "toolkit")
        assert agent.llm == default_kwargs["llm"]
        assert agent.toolkit.vectorstores == default_kwargs["vectorstores"]

    async def test_agent_component_latest(self, component_class, default_kwargs):
        # Arrange
        component = component_class(**default_kwargs)

        # Act
        result = await component.run()

        # Assert
        assert result is not None
