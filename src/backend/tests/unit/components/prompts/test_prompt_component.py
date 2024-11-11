import pytest
from langflow.components.prompts import PromptComponent

from tests.base import DID_NOT_EXIST, ComponentTestBase
from tests.integration.utils import build_component_instance_for_tests


@pytest.mark.usefixtures("client")
class TestPromptComponent(ComponentTestBase):
    DEFAULT_KWARGS = {"template": "Hello {name}!", "name": "John", "_session_id": "123"}
    FILE_NAMES_MAPPING = {
        "1.0.15": "Prompt",
        "1.0.16": "Prompt",
        "1.0.17": "Prompt",
        "1.0.18": "Prompt",
        "1.0.19": "Prompt",
    }

    def test_post_code_processing(self):
        component = PromptComponent(**self.DEFAULT_KWARGS)
        frontend_node = component.to_frontend_node()
        node_data = frontend_node["data"]["node"]
        assert node_data["template"]["template"]["value"] == "Hello {name}!"
        assert "name" in node_data["custom_fields"]["template"]
        assert "name" in node_data["template"]
        assert node_data["template"]["name"]["value"] == "John"

    @pytest.mark.parametrize(("version", "file_name"), list(FILE_NAMES_MAPPING.items()))
    def test_prompt_component_versions(self, version, file_name):
        if file_name is DID_NOT_EXIST:
            pytest.skip(f"Prompt component did not exist in version {version}")
        result = build_component_instance_for_tests(version, file_name=file_name, **self.DEFAULT_KWARGS)
        assert result is not None

    def test_prompt_component_latest(self):
        result = PromptComponent(**self.DEFAULT_KWARGS)()
        assert result is not None
