import pytest
from langflow.components.langchain_utilities import JsonAgentComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestJsonAgentComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return JsonAgentComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"llm": "mock_llm", "path": "mock_path.json", "_session_id": "123"}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "agents", "file_name": "JsonAgent"},
            {"version": "1.1.0", "module": "agents", "file_name": "json_agent"},
        ]

    def test_build_agent_with_yaml(self, component_class, default_kwargs):
        default_kwargs["path"] = "mock_path.yaml"
        component = component_class(**default_kwargs)
        agent = component.build_agent()
        assert agent is not None

    def test_build_agent_with_json(self, component_class, default_kwargs):
        default_kwargs["path"] = "mock_path.json"
        component = component_class(**default_kwargs)
        agent = component.build_agent()
        assert agent is not None

    async def test_latest_version(self, component_class, default_kwargs):
        component_instance = await self.component_setup(component_class, default_kwargs)
        result = await component_instance.run()
        assert result is not None, "Component returned None for the latest version."
