import pytest
from lfx.components.processing import PromptComponent

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
        return [
            {"version": "1.0.19", "module": "prompts", "file_name": "Prompt"},
            {"version": "1.1.0", "module": "prompts", "file_name": "prompt"},
            {"version": "1.1.1", "module": "prompts", "file_name": "prompt"},
        ]

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
