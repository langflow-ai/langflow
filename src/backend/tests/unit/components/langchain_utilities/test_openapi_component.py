import pytest

from langflow.components.langchain_utilities import OpenAPIAgentComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestOpenAPIAgentComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return OpenAPIAgentComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"llm": "mock_llm", "path": "mock_path.yaml", "allow_dangerous_requests": False, "_session_id": "123"}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "agents", "file_name": "OpenAPIAgent"},
        ]

    def test_build_agent_with_yaml(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        agent = component.build_agent()
        assert agent is not None

    def test_build_agent_with_json(self, component_class, default_kwargs):
        default_kwargs["path"] = "mock_path.json"
        component = component_class(**default_kwargs)
        agent = component.build_agent()
        assert agent is not None

    def test_invalid_file_type(self, component_class):
        with pytest.raises(ValueError):
            component_class(llm="mock_llm", path="mock_path.txt", allow_dangerous_requests=False)
