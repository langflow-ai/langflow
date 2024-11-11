import pytest
from langflow.components.prompts import PromptComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestPromptComponent(ComponentTestBaseWithClient):
    component_class = PromptComponent
    DEFAULT_KWARGS = {"template": "Hello {name}!", "name": "John", "_session_id": "123"}
    FILE_NAMES_MAPPING = {
        "1.0.15": "Prompt",
        "1.0.16": "Prompt",
        "1.0.17": "Prompt",
        "1.0.18": "Prompt",
        "1.0.19": "Prompt",
    }

    def test_post_code_processing(self):
        component = self.component_class(**self.DEFAULT_KWARGS)
        frontend_node = component.to_frontend_node()
        node_data = frontend_node["data"]["node"]
        assert node_data["template"]["template"]["value"] == "Hello {name}!"
        assert "name" in node_data["custom_fields"]["template"]
        assert "name" in node_data["template"]
        assert node_data["template"]["name"]["value"] == "John"

    def test_prompt_component_latest(self):
        result = PromptComponent(**self.DEFAULT_KWARGS)()
        assert result is not None
