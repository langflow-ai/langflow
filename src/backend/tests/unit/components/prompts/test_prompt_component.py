import pytest
from langflow.components.prompts import PromptComponent

from tests.constants import SUPPORTED_VERSIONS
from tests.integration.utils import build_component_instance_for_tests


@pytest.mark.usefixtures("client")
class TestPromptComponent:
    DEFAULT_KWARGS = {"template": "Hello {name}!", "name": "John", "_session_id": "123"}

    def test_post_code_processing(self):
        component = PromptComponent(**self.DEFAULT_KWARGS)
        frontend_node = component.to_frontend_node()
        node_data = frontend_node["data"]["node"]
        assert node_data["template"]["template"]["value"] == "Hello {name}!"
        assert "name" in node_data["custom_fields"]["template"]
        assert "name" in node_data["template"]
        assert node_data["template"]["name"]["value"] == "John"

    @pytest.mark.parametrize("version", SUPPORTED_VERSIONS)
    def test_prompt_component_versions(self, version):
        result = build_component_instance_for_tests(version, **self.DEFAULT_KWARGS)
        assert result is not None

    def test_prompt_component_latest(self):
        result = PromptComponent(**self.DEFAULT_KWARGS)()
        assert result is not None
