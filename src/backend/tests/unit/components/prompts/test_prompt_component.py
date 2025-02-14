import pytest
from langflow.components.prompts import PromptComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestPromptComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return PromptComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"template": "Hello {name}!", "name": "John", "_session_id": "123"}

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""
        return []

    @pytest.fixture
    def module(self):
        """Return the module name for the component."""
        return "prompts"

    @pytest.fixture
    def file_name(self):
        """Return the file name for the component."""
        return "prompt"

    def test_post_code_processing(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        frontend_node = component.to_frontend_node()
        node_data = frontend_node["data"]["node"]
        assert node_data["template"]["template"]["value"] == "Hello {name}!"
        assert "name" in node_data["custom_fields"]["template"]
        assert "name" in node_data["template"]
        assert node_data["template"]["name"]["value"] == "John"

    def test_prompt_component_latest(self, component_class, default_kwargs):
        result = component_class(**default_kwargs)()
        assert result is not None
